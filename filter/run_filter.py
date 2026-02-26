#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import read_jsonl, write_json, write_jsonl
from filter.filter_stages import (
    compute_anchor_semantic_scores,
    compute_paired_anchor_semantic_scores,
    build_image_embeddings,
    compute_anchor_ood_scores,
    compute_consistency_scores,
    compute_duplicate_similarity,
    compute_multicrop_consistency_scores,
    compute_prompt_margin_scores,
    compute_prompt_scores,
    compute_quality_scores,
    fit_anchor_ood_stats,
)
from filter.manifest_builder import build_input_manifest_from_config


def stable_score(sample_id: str) -> float:
    digest = hashlib.sha256(sample_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def build_stub_manifest(total_count: int, real_ratio: float) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    real_count = int(total_count * real_ratio)
    synth_count = total_count - real_count
    for i in range(real_count):
        sample_id = f"real_{i:04d}"
        rows.append(
            {
                "sample_id": sample_id,
                "source": "real",
                "image_path": f"data/real/{sample_id}.jpg",
            }
        )
    for i in range(synth_count):
        sample_id = f"synth_{i:04d}"
        rows.append(
            {
                "sample_id": sample_id,
                "source": "synthetic",
                "image_path": f"data/synth/{sample_id}.jpg",
            }
        )
    return rows


def choose_decision(score: float, accept_threshold: float, uncertain_low: float, uncertain_high: float) -> str:
    if score >= accept_threshold:
        return "accept"
    if uncertain_low <= score < uncertain_high:
        return "uncertain"
    return "reject"


def _apply_topk_review_selection(
    score_rows: List[Dict[str, Any]],
    filter_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    policy_cfg = dict(filter_cfg.get("policy", {}))
    ranking_cfg = dict(policy_cfg.get("ranking_review", {}))
    if not bool(ranking_cfg.get("enabled", False)):
        return {"enabled": False}

    target_source = str(ranking_cfg.get("target_source", "synthetic")).strip()
    rank_metric = str(ranking_cfg.get("rank_metric", "final_score")).strip()
    keep_top_k = int(ranking_cfg.get("keep_top_k", 0))
    keep_top_ratio = float(ranking_cfg.get("keep_top_ratio", 0.0))
    review_rest = bool(ranking_cfg.get("review_rest", True))

    candidates = [r for r in score_rows if str(r.get("source", "")) == target_source]
    sorted_rows = sorted(candidates, key=lambda r: float(r.get(rank_metric, 0.0)), reverse=True)
    total = len(sorted_rows)

    keep_n = 0
    if keep_top_k > 0:
        keep_n = min(total, keep_top_k)
    elif keep_top_ratio > 0.0:
        keep_n = min(total, max(0, int(round(total * keep_top_ratio))))

    keep_ids = {str(r.get("sample_id", "")) for r in sorted_rows[:keep_n]}
    rank_map = {str(r.get("sample_id", "")): idx + 1 for idx, r in enumerate(sorted_rows)}

    accept_count = 0
    uncertain_count = 0
    reject_count = 0
    for row in score_rows:
        sid = str(row.get("sample_id", ""))
        src = str(row.get("source", ""))
        if src != target_source:
            if str(row.get("decision", "")) == "accept":
                accept_count += 1
            elif str(row.get("decision", "")) == "uncertain":
                uncertain_count += 1
            else:
                reject_count += 1
            continue

        row["rank_metric"] = rank_metric
        row["rank_value"] = round(float(row.get(rank_metric, 0.0)), 6)
        row["rank_position"] = int(rank_map.get(sid, 0))

        if sid in keep_ids:
            row["decision"] = "accept"
            row["keep"] = True
            row["decision_basis"] = "policy_ranking_topk_keep"
            row["gate_fail"] = ""
            accept_count += 1
        else:
            row["decision"] = "uncertain" if review_rest else "reject"
            row["keep"] = False
            row["decision_basis"] = "policy_ranking_review_queue" if review_rest else "policy_ranking_topk_reject"
            if row["decision"] == "uncertain":
                uncertain_count += 1
            else:
                reject_count += 1

    return {
        "enabled": True,
        "target_source": target_source,
        "rank_metric": rank_metric,
        "candidate_total": total,
        "keep_top_k": keep_top_k,
        "keep_top_ratio": keep_top_ratio,
        "keep_count": keep_n,
        "review_rest": review_rest,
        "accept_after_selection": accept_count,
        "uncertain_after_selection": uncertain_count,
        "reject_after_selection": reject_count,
    }


def _annotate_phase1_compare_log_with_final_decision(
    report_extra: Dict[str, Any],
    score_rows: List[Dict[str, Any]],
) -> None:
    phase1 = report_extra.get("phase1_semantic", {})
    if not isinstance(phase1, dict):
        return
    path_raw = str(phase1.get("compare_log_path", "")).strip()
    if not path_raw:
        return
    path = Path(path_raw)
    if not path.exists():
        return

    rows = read_jsonl(path)
    by_sid = {str(r.get("sample_id", "")): r for r in score_rows}
    out: List[Dict[str, Any]] = []
    for row in rows:
        sid = str(row.get("sample_id", ""))
        score = by_sid.get(sid)
        if score is None:
            out.append(row)
            continue
        row2 = dict(row)
        row2["decision_final"] = str(score.get("decision", ""))
        row2["decision_basis_final"] = str(score.get("decision_basis", ""))
        if "rank_position" in score:
            row2["rank_position"] = int(score.get("rank_position", 0))
        if "rank_value" in score:
            row2["rank_value"] = float(score.get("rank_value", 0.0))
        out.append(row2)
    write_jsonl(path, out)


def quantile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    q = max(0.0, min(1.0, q))
    arr = sorted(float(v) for v in values)
    if len(arr) == 1:
        return arr[0]
    pos = q * (len(arr) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(arr) - 1)
    frac = pos - lo
    return arr[lo] * (1.0 - frac) + arr[hi] * frac


def load_clip_runtime(model_id: str, device_cfg: str) -> Tuple[Any, Any, Any]:
    try:
        import torch  # type: ignore
        from transformers import CLIPModel, CLIPProcessor  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "pcs_clip mode requires `torch` and `transformers`. "
            "Install them first, e.g. `pip install torch transformers`."
        ) from exc

    if device_cfg == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = device_cfg

    model = CLIPModel.from_pretrained(model_id)
    processor = CLIPProcessor.from_pretrained(model_id)
    model.to(device)
    model.eval()
    return torch, model, processor


def image_embedding(
    image_path: Path,
    torch_mod: Any,
    model: Any,
    processor: Any,
    device: str,
) -> Any:
    from PIL import Image

    with Image.open(image_path) as img:
        image = img.convert("RGB")
        inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch_mod.no_grad():
        feat = model.get_image_features(**inputs)
        feat = feat / feat.norm(dim=-1, keepdim=True).clamp(min=1e-12)
    return feat[0]


def cosine_similarity(vec_a: Any, vec_b: Any) -> float:
    return float((vec_a * vec_b).sum().item())


def make_grid_boxes(width: int, height: int, rows: int, cols: int) -> List[Tuple[int, int, int, int]]:
    boxes: List[Tuple[int, int, int, int]] = []
    for r in range(rows):
        y0 = (height * r) // rows
        y1 = (height * (r + 1)) // rows
        for c in range(cols):
            x0 = (width * c) // cols
            x1 = (width * (c + 1)) // cols
            boxes.append((x0, y0, x1, y1))
    return boxes


def perturb_image_by_block_shuffle(
    image_path: Path,
    out_path: Path,
    rng: random.Random,
    grid_rows: int,
    grid_cols: int,
    swap_ratio: float,
    min_swaps: int,
    max_swaps: int,
) -> None:
    from PIL import Image

    with Image.open(image_path) as img:
        image = img.convert("RGB")
        width, height = image.size
        boxes = make_grid_boxes(width, height, grid_rows, grid_cols)
        total_blocks = len(boxes)
        target_swaps = int(round(total_blocks * max(0.0, min(1.0, swap_ratio))))
        swaps = max(min_swaps, target_swaps)
        swaps = min(swaps, max_swaps, total_blocks)
        if swaps < 2:
            swaps = 2 if total_blocks >= 2 else 1
        picked = list(range(total_blocks))
        rng.shuffle(picked)
        picked = picked[:swaps]

        out = image.copy()
        patches = {idx: image.crop(boxes[idx]) for idx in picked}
        size_groups: Dict[Tuple[int, int], List[int]] = {}
        for idx in picked:
            box = boxes[idx]
            key = (box[2] - box[0], box[3] - box[1])
            size_groups.setdefault(key, []).append(idx)
        for group in size_groups.values():
            shuffled_group = group[:]
            rng.shuffle(shuffled_group)
            for src_idx, dst_idx in zip(group, shuffled_group):
                out.paste(patches[src_idx], boxes[dst_idx])
        out.save(out_path)


def run_stub_filter(
    rows: List[Dict[str, Any]],
    accept_threshold: float,
    uncertain_low: float,
    uncertain_high: float,
) -> List[Dict[str, Any]]:
    score_rows: List[Dict[str, Any]] = []
    for row in rows:
        sample_id = str(row.get("sample_id", "unknown"))
        score = stable_score(sample_id)
        decision = choose_decision(score, accept_threshold, uncertain_low, uncertain_high)
        score_rows.append(
            {
                "sample_id": sample_id,
                "source": row.get("source"),
                "score_asf": round(score, 6),
                "score_pcs": round(1.0 - abs(score - 0.5) * 2.0, 6),
                "decision": decision,
                "decision_basis": "stub_score_asf",
            }
        )
    return score_rows


def run_pcs_clip_filter(
    rows: List[Dict[str, Any]],
    filter_dir: Path,
    accept_threshold: float,
    uncertain_low: float,
    uncertain_high: float,
    filter_cfg: Dict[str, Any],
) -> List[Dict[str, Any]]:
    pcs_cfg = dict(filter_cfg.get("pcs", {}))
    model_id = str(filter_cfg.get("clip_model_id", "openai/clip-vit-base-patch32"))
    grid_rows = int(pcs_cfg.get("grid_rows", 4))
    grid_cols = int(pcs_cfg.get("grid_cols", 4))
    repeats = int(pcs_cfg.get("repeats", 4))
    swap_ratio = float(pcs_cfg.get("swap_ratio", 0.4))
    min_swaps = int(pcs_cfg.get("min_swaps", 2))
    max_swaps = int(pcs_cfg.get("max_swaps", 8))
    seed_base = int(pcs_cfg.get("seed_base", 20260214))
    device = str(pcs_cfg.get("device", "auto"))
    synthetic_only = bool(pcs_cfg.get("synthetic_only", True))
    keep_real_always = bool(pcs_cfg.get("keep_real_always", True))
    keep_perturbed_images = bool(pcs_cfg.get("keep_perturbed_images", False))

    perturb_dir = filter_dir / "perturb_preview"
    if keep_perturbed_images:
        perturb_dir.mkdir(parents=True, exist_ok=True)

    torch_mod, model, processor = load_clip_runtime(model_id, device)
    device_runtime = next(model.parameters()).device.type

    score_rows: List[Dict[str, Any]] = []
    for row in rows:
        sample_id = str(row.get("sample_id", "unknown"))
        source = str(row.get("source", ""))
        image_path = Path(str(row.get("image_path", "")))
        asf_score = stable_score(sample_id)

        if source == "real" and keep_real_always:
            score_rows.append(
                {
                    "sample_id": sample_id,
                    "source": source,
                    "score_asf": round(asf_score, 6),
                    "score_pcs": 1.0,
                    "decision": "accept",
                    "decision_basis": "keep_real_always",
                    "pcs_model_id": model_id,
                    "pcs_device": device_runtime,
                }
            )
            continue

        if synthetic_only and source != "synthetic":
            decision = choose_decision(asf_score, accept_threshold, uncertain_low, uncertain_high)
            score_rows.append(
                {
                    "sample_id": sample_id,
                    "source": source,
                    "score_asf": round(asf_score, 6),
                    "score_pcs": round(asf_score, 6),
                    "decision": decision,
                    "decision_basis": "stub_score_asf_non_synthetic",
                    "pcs_model_id": model_id,
                    "pcs_device": device_runtime,
                }
            )
            continue

        if not image_path.exists():
            score_rows.append(
                {
                    "sample_id": sample_id,
                    "source": source,
                    "score_asf": round(asf_score, 6),
                    "score_pcs": 0.0,
                    "decision": "reject",
                    "decision_basis": "missing_image",
                    "pcs_model_id": model_id,
                    "pcs_device": device_runtime,
                }
            )
            continue

        orig_emb = image_embedding(image_path, torch_mod, model, processor, device_runtime)
        sims: List[float] = []
        for k in range(max(1, repeats)):
            digest = hashlib.sha256(f"{sample_id}|{seed_base}|{k}".encode("utf-8")).hexdigest()
            rng = random.Random(int(digest[:8], 16))
            tmp_path = (
                perturb_dir / f"{sample_id}.perturb_{k:02d}.png"
                if keep_perturbed_images
                else filter_dir / f".tmp_{sample_id}_{k}.png"
            )
            perturb_image_by_block_shuffle(
                image_path=image_path,
                out_path=tmp_path,
                rng=rng,
                grid_rows=max(1, grid_rows),
                grid_cols=max(1, grid_cols),
                swap_ratio=swap_ratio,
                min_swaps=max(1, min_swaps),
                max_swaps=max(1, max_swaps),
            )
            per_emb = image_embedding(tmp_path, torch_mod, model, processor, device_runtime)
            sims.append(cosine_similarity(orig_emb, per_emb))
            if not keep_perturbed_images and tmp_path.exists():
                tmp_path.unlink()

        pcs_score = sum(sims) / len(sims) if sims else 0.0
        decision = choose_decision(pcs_score, accept_threshold, uncertain_low, uncertain_high)
        score_rows.append(
            {
                "sample_id": sample_id,
                "source": source,
                "score_asf": round(asf_score, 6),
                "score_pcs": round(pcs_score, 6),
                "pcs_similarity_min": round(min(sims), 6) if sims else 0.0,
                "pcs_similarity_max": round(max(sims), 6) if sims else 0.0,
                "pcs_similarity_mean": round(pcs_score, 6),
                "pcs_repeats": len(sims),
                "decision": decision,
                "decision_basis": "score_pcs",
                "pcs_model_id": model_id,
                "pcs_device": device_runtime,
            }
        )
    return score_rows


def _stage_enabled_map(filter_cfg: Dict[str, Any]) -> Dict[str, bool]:
    defaults: Dict[str, bool] = {
        "semantic_anchor": True,
        "prompt_score": True,
        "prompt_margin": True,
        "consistency": True,
        "multicrop": True,
        "anchor_ood": True,
        "dedup": True,
        "quality": True,
    }
    stages_cfg = filter_cfg.get("stages")
    if stages_cfg is None:
        return defaults

    out = dict(defaults)
    if isinstance(stages_cfg, dict):
        for key, value in stages_cfg.items():
            if isinstance(value, dict):
                out[str(key)] = bool(value.get("enabled", True))
            else:
                out[str(key)] = bool(value)
        return out

    if isinstance(stages_cfg, list):
        for item in stages_cfg:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("id", "")).strip()
            if not sid:
                continue
            out[sid] = bool(item.get("enabled", True))
    return out


def _resolve_prompt_score_mode(clip_cfg: Dict[str, Any], model_id: str) -> str:
    explicit = str(clip_cfg.get("prompt_score_mode", "")).strip().lower()
    if explicit:
        return explicit
    if "siglip" in model_id.strip().lower():
        return "siglip_sigmoid"
    return "cosine"


def _resolve_filter_prompt_text(
    filter_cfg: Dict[str, Any],
    *,
    config_path: Path,
) -> str:
    clip_cfg = filter_cfg.get("clip")
    if not isinstance(clip_cfg, dict):
        return ""

    prompt_text = str(clip_cfg.get("prompt_text", "")).strip()
    if prompt_text:
        return "clip.prompt_text"

    template_file = str(clip_cfg.get("prompt_template_file", "")).strip()
    if template_file:
        path = Path(template_file)
        if not path.is_absolute():
            path = (config_path.parent / path).resolve()
        clip_cfg["prompt_text"] = path.read_text(encoding="utf-8").strip()
        return "clip.prompt_template_file"

    generate_cfg_path = str(clip_cfg.get("prompt_from_generate_config", "")).strip()
    if not generate_cfg_path:
        return ""
    gen_path = Path(generate_cfg_path)
    if not gen_path.is_absolute():
        gen_path = (config_path.parent / gen_path).resolve()
    gen_cfg = load_config(gen_path)
    prompt_cfg = (
        gen_cfg.get("generate", {})
        .get("comfyui", {})
        .get("prompt", {})
    )
    if not isinstance(prompt_cfg, dict):
        return ""

    gen_template_file = str(prompt_cfg.get("template_file", "")).strip()
    if gen_template_file:
        p = Path(gen_template_file)
        if not p.is_absolute():
            p = (gen_path.parent / p).resolve()
        clip_cfg["prompt_text"] = p.read_text(encoding="utf-8").strip()
        return "clip.prompt_from_generate_config.template_file"

    gen_text_template = prompt_cfg.get("text_template")
    if isinstance(gen_text_template, str) and gen_text_template.strip():
        clip_cfg["prompt_text"] = gen_text_template.strip()
        return "clip.prompt_from_generate_config.text_template"

    gen_text = str(prompt_cfg.get("text", "")).strip()
    if gen_text:
        clip_cfg["prompt_text"] = gen_text
        return "clip.prompt_from_generate_config.text"
    return ""


def _resolve_filter_input_manifest(
    *,
    filter_cfg: Dict[str, Any],
    run_dir: Path,
) -> tuple[Path | None, str]:
    input_manifest = filter_cfg.get("input_manifest")
    if input_manifest:
        return Path(str(input_manifest)), "filter.input_manifest"

    auto_from_generate = bool(filter_cfg.get("auto_input_from_generate_mixed", True))
    if auto_from_generate:
        mixed_manifest = run_dir / "generate" / "mixed_manifest.jsonl"
        if mixed_manifest.exists():
            return mixed_manifest, "run_dir/generate/mixed_manifest.jsonl"

    return None, ""


def _is_real_guided_synth(row: Dict[str, Any], phase1_cfg: Dict[str, Any]) -> bool:
    if str(row.get("source", "")) != "synthetic":
        return False
    marker_fields = [str(x) for x in phase1_cfg.get(
        "guided_marker_fields",
        [
            "anchor_real_sample_id",
            "anchor_real_image_path",
            "effective_anchor_input",
            "effective_anchor_inputs",
        ],
    )]
    for field in marker_fields:
        val = row.get(field)
        if isinstance(val, str) and val.strip():
            return True
        if isinstance(val, dict) and val:
            return True
    return False


def build_phase1_semantic_scores(
    rows: List[Dict[str, Any]],
    semantic_scores: Dict[str, Dict[str, float]],
    paired_scores: Dict[str, Dict[str, float]],
    prompt_scores: Dict[str, float],
    phase1_cfg: Dict[str, Any],
) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    enabled = bool(phase1_cfg.get("enabled", False))
    if not enabled:
        out_disabled: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            sid = str(row.get("sample_id", ""))
            out_disabled[sid] = {
                "s_phase1_semantic": float(semantic_scores.get(sid, {}).get("s_semantic_anchor", 0.0)),
                "s_phase1_semantic_source": "semantic_anchor",
            }
        return out_disabled, {"enabled": False}

    guided_source = str(phase1_cfg.get("guided_source", "semantic_pair")).strip().lower()
    prompt_only_source = str(phase1_cfg.get("prompt_only_source", "prompt_score")).strip().lower()
    fallback_source = str(phase1_cfg.get("fallback_source", "semantic_anchor")).strip().lower()
    guided_fusion_cfg = dict(phase1_cfg.get("guided_fusion", {}))
    guided_fusion_enabled = bool(guided_fusion_cfg.get("enabled", False))
    guided_fusion_method = str(guided_fusion_cfg.get("method", "weighted_sum")).strip().lower()
    pair_weight = float(guided_fusion_cfg.get("pair_weight", 0.7))
    prompt_weight = float(guided_fusion_cfg.get("prompt_weight", 0.3))
    w_sum = pair_weight + prompt_weight
    if w_sum <= 0.0:
        pair_weight = 1.0
        prompt_weight = 0.0
    else:
        pair_weight = pair_weight / w_sum
        prompt_weight = prompt_weight / w_sum

    def _fuse_guided_score(pair_score: float, prompt_score: float) -> float:
        a = max(0.0, min(1.0, pair_score))
        b = max(0.0, min(1.0, prompt_score))
        if guided_fusion_method == "geometric_mean":
            eps = 1e-12
            return float((max(eps, a) ** pair_weight) * (max(eps, b) ** prompt_weight))
        if guided_fusion_method == "harmonic_mean":
            eps = 1e-12
            denom = (pair_weight / max(eps, a)) + (prompt_weight / max(eps, b))
            if denom <= 0.0:
                return 0.0
            return float(1.0 / denom)
        # default weighted fusion
        return float(pair_weight * a + prompt_weight * b)

    out: Dict[str, Dict[str, Any]] = {}
    guided_count = 0
    prompt_only_count = 0
    source_counter: Dict[str, int] = {}

    for row in rows:
        sid = str(row.get("sample_id", ""))
        is_guided = _is_real_guided_synth(row=row, phase1_cfg=phase1_cfg)
        if is_guided:
            guided_count += 1
        else:
            if str(row.get("source", "")) == "synthetic":
                prompt_only_count += 1

        selected_source = fallback_source
        value = float(semantic_scores.get(sid, {}).get("s_semantic_anchor", 0.0))

        if is_guided and guided_source == "semantic_pair":
            pair = paired_scores.get(sid, {})
            if float(pair.get("s_semantic_pair_hit", 0.0)) > 0.0:
                pair_val = float(pair.get("s_semantic_pair", 0.0))
                if guided_fusion_enabled:
                    selected_source = "semantic_pair_fused"
                    prompt_val = float(prompt_scores.get(sid, 0.0))
                    value = _fuse_guided_score(pair_score=pair_val, prompt_score=prompt_val)
                else:
                    selected_source = "semantic_pair"
                    value = pair_val
        elif (not is_guided) and str(row.get("source", "")) == "synthetic" and prompt_only_source == "prompt_score":
            selected_source = "prompt_score"
            value = float(prompt_scores.get(sid, 0.0))

        if selected_source == fallback_source:
            if fallback_source == "prompt_score":
                value = float(prompt_scores.get(sid, 0.0))
            elif fallback_source == "semantic_pair":
                value = float(paired_scores.get(sid, {}).get("s_semantic_pair", 0.0))
            else:
                value = float(semantic_scores.get(sid, {}).get("s_semantic_anchor", 0.0))

        source_counter[selected_source] = source_counter.get(selected_source, 0) + 1
        out[sid] = {
            "s_phase1_semantic": max(0.0, min(1.0, value)),
            "s_phase1_semantic_source": selected_source,
        }

    return out, {
        "enabled": True,
        "guided_source": guided_source,
        "prompt_only_source": prompt_only_source,
        "fallback_source": fallback_source,
        "guided_fusion": {
            "enabled": guided_fusion_enabled,
            "method": guided_fusion_method,
            "pair_weight": pair_weight,
            "prompt_weight": prompt_weight,
        },
        "guided_synth_count": guided_count,
        "prompt_only_synth_count": prompt_only_count,
        "source_counter": source_counter,
    }


def _as_op(op_raw: str) -> str:
    op = op_raw.strip()
    if op in {">=", "gte"}:
        return ">="
    if op in {"<=", "lte"}:
        return "<="
    if op in {">", "gt"}:
        return ">"
    if op in {"<", "lt"}:
        return "<"
    if op in {"==", "eq"}:
        return "=="
    raise ValueError(f"unsupported gate op: {op_raw}")


def _eval_gate(metric_value: float, op: str, threshold: float) -> bool:
    if op == ">=":
        return metric_value >= threshold
    if op == "<=":
        return metric_value <= threshold
    if op == ">":
        return metric_value > threshold
    if op == "<":
        return metric_value < threshold
    if op == "==":
        return abs(metric_value - threshold) <= 1e-12
    return False


def _gate_applies_to_row(
    gate_cfg: Dict[str, Any],
    row: Dict[str, Any],
    phase1_source: str,
) -> bool:
    source = str(row.get("source", "")).strip()
    src_in = [str(x).strip() for x in gate_cfg.get("sources", []) if str(x).strip()]
    src_not_in = [str(x).strip() for x in gate_cfg.get("sources_exclude", []) if str(x).strip()]
    p1_in = [str(x).strip() for x in gate_cfg.get("phase1_sources", []) if str(x).strip()]
    p1_not_in = [str(x).strip() for x in gate_cfg.get("phase1_sources_exclude", []) if str(x).strip()]

    if src_in and source not in set(src_in):
        return False
    if src_not_in and source in set(src_not_in):
        return False
    phase1_candidates = {phase1_source}
    if phase1_source.startswith("semantic_pair"):
        phase1_candidates.add("semantic_pair")
    if phase1_source.startswith("prompt_score"):
        phase1_candidates.add("prompt_score")

    if p1_in and not (set(p1_in) & phase1_candidates):
        return False
    if p1_not_in and (set(p1_not_in) & phase1_candidates):
        return False
    return True


def _resolve_gate_threshold(
    gate_cfg: Dict[str, Any],
    metric_name: str,
    calib_rows: List[Dict[str, Any]],
    metric_getter: Any,
) -> float:
    explicit = gate_cfg.get("threshold")
    if explicit is not None:
        return float(explicit)

    token = str(gate_cfg.get("threshold_from", "")).strip().lower()
    if not token:
        return 0.0
    if not token.startswith("q"):
        raise ValueError(f"unsupported threshold_from token: {token}")

    # q05 / q95 / q99
    q_part = token[1:]
    if "_" in q_part:
        q_str, source_name = q_part.split("_", 1)
        calib = [r for r in calib_rows if str(r.get("source", "")) == source_name]
        if not calib:
            calib = calib_rows
    else:
        q_str = q_part
        calib = calib_rows
    q = float(q_str) / 100.0
    vals = [float(metric_getter(metric_name, row)) for row in calib]
    return quantile(vals, q)


def _resolve_row_prompt_text(row: Dict[str, Any], prompt_field: str, default_prompt: str) -> str:
    row_prompt = str(row.get(prompt_field, "")).strip() if prompt_field else ""
    return row_prompt or default_prompt


def run_composed_clip_filter(
    rows: List[Dict[str, Any]],
    filter_dir: Path,
    accept_threshold: float,
    uncertain_low: float,
    uncertain_high: float,
    filter_cfg: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    clip_cfg = dict(filter_cfg.get("clip", {}))
    model_id = str(
        clip_cfg.get(
            "model_id",
            filter_cfg.get("clip_model_id", "openai/clip-vit-base-patch32"),
        )
    )
    device = str(clip_cfg.get("device", "auto"))
    prompt_text = str(clip_cfg.get("prompt_text", filter_cfg.get("prompt_text", "")))
    prompt_score_mode = _resolve_prompt_score_mode(clip_cfg=clip_cfg, model_id=model_id)
    neg_prompts = [str(x) for x in clip_cfg.get("negative_prompts", [])]
    cache_path = Path(str(clip_cfg.get("embed_cache_path", filter_dir / "clip_embed_cache.json")))
    phase1_cfg = dict(filter_cfg.get("phase1_semantic", {}))
    prompt_field = str(phase1_cfg.get("prompt_field", "effective_prompt_text"))

    stages_enabled = _stage_enabled_map(filter_cfg)
    keep_real_always = bool(filter_cfg.get("keep_real_always", True))
    dedup_cfg = dict(filter_cfg.get("dedup", {}))
    dedup_synthetic_only = bool(dedup_cfg.get("synthetic_only", False))

    score_cfg = dict(filter_cfg.get("score", {}))
    default_weighted = {
        "s_semantic_anchor": float(score_cfg.get("w_semantic_anchor", 0.0)),
        "s_prompt": float(score_cfg.get("w_prompt", 0.30)),
        "s_consistency": float(score_cfg.get("w_consistency", 0.35)),
        "s_multicrop_consistency": float(score_cfg.get("w_multicrop", 0.0)),
        "dedup_good": float(score_cfg.get("w_dedup", 0.20)),
        "blur_norm": float(score_cfg.get("w_blur", 0.10)),
        "exposure_score": float(score_cfg.get("w_exposure", 0.05)),
        "ood_score": float(score_cfg.get("w_ood", 0.0)),
    }

    embeddings, runtime, cache_stats = build_image_embeddings(
        rows=rows,
        model_id=model_id,
        device_cfg=device,
        cache_path=cache_path,
    )

    sid_list = [str(r.get("sample_id", "")) for r in rows]
    prompt_scores: Dict[str, float] = {sid: 0.0 for sid in sid_list}
    phase1_scores: Dict[str, Dict[str, Any]] = {
        sid: {"s_phase1_semantic": 0.0, "s_phase1_semantic_source": "semantic_anchor"} for sid in sid_list
    }
    semantic_scores: Dict[str, Dict[str, float]] = {
        sid: {
            "s_semantic_anchor_raw": 0.0,
            "s_semantic_anchor": 0.0,
        }
        for sid in sid_list
    }
    prompt_margin_scores: Dict[str, Dict[str, float]] = {
        sid: {
            "s_prompt_pos": 0.0,
            "s_prompt_neg_max": 0.0,
            "s_prompt_margin": -1.0,
            "s_prompt_margin_norm": 0.0,
        }
        for sid in sid_list
    }
    cons_scores: Dict[str, Dict[str, float]] = {
        sid: {
            "s_consistency": 0.0,
            "pcs_similarity_min": 0.0,
            "pcs_similarity_max": 0.0,
            "pcs_similarity_mean": 0.0,
            "pcs_repeats": 0.0,
        }
        for sid in sid_list
    }
    paired_scores: Dict[str, Dict[str, Any]] = {
        sid: {
            "s_semantic_pair_raw": 0.0,
            "s_semantic_pair": 0.0,
            "s_semantic_pair_hit": 0.0,
            "anchor_sid_resolved": "",
            "pair_miss_reason": "",
        }
        for sid in sid_list
    }
    multicrop_scores: Dict[str, Dict[str, float]] = {
        sid: {
            "s_multicrop_consistency": 0.0,
            "multicrop_pair_sim_min": 0.0,
            "multicrop_pair_sim_max": 0.0,
            "multicrop_pair_sim_mean": 0.0,
            "multicrop_views": 0.0,
        }
        for sid in sid_list
    }
    ood_scores: Dict[str, Dict[str, float]] = {
        sid: {
            "ood_md2": 0.0,
            "ood_score": 1.0,
        }
        for sid in sid_list
    }
    dup_scores: Dict[str, float] = {sid: 0.0 for sid in sid_list}
    quality_scores: Dict[str, Dict[str, float]] = {
        sid: {
            "blur_score": 0.0,
            "blur_norm": 0.0,
            "exposure_score": 0.0,
        }
        for sid in sid_list
    }
    semantic_cfg = dict(filter_cfg.get("semantic_anchor", {}))
    if stages_enabled.get("semantic_anchor", True):
        semantic_scores, semantic_state = compute_anchor_semantic_scores(
            rows=rows,
            image_embeddings=embeddings,
            cfg=semantic_cfg,
        )
    else:
        semantic_state = {
            "enabled": False,
            "reason": "disabled_by_stage_config",
            "anchor_count": 0,
            "reduce": str(semantic_cfg.get("reduce", "median")),
        }

    if stages_enabled.get("prompt_score", True):
        prompt_scores = compute_prompt_scores(
            rows=rows,
            image_embeddings=embeddings,
            runtime=runtime,
            prompt_text=prompt_text,
            prompt_score_mode=prompt_score_mode,
            prompt_field=prompt_field,
        )
    elif bool(phase1_cfg.get("enabled", False)):
        prompt_scores = compute_prompt_scores(
            rows=rows,
            image_embeddings=embeddings,
            runtime=runtime,
            prompt_text=prompt_text,
            prompt_score_mode=prompt_score_mode,
            prompt_field=prompt_field,
        )
    if stages_enabled.get("prompt_margin", True):
        prompt_margin_scores = compute_prompt_margin_scores(
            rows=rows,
            image_embeddings=embeddings,
            runtime=runtime,
            pos_prompt=prompt_text,
            neg_prompts=neg_prompts,
            prompt_score_mode=prompt_score_mode,
        )
    if stages_enabled.get("consistency", True):
        cons_scores = compute_consistency_scores(
            rows=rows,
            image_embeddings=embeddings,
            runtime=runtime,
            cfg=dict(filter_cfg.get("pcs", {})),
            work_dir=filter_dir,
        )
    if stages_enabled.get("multicrop", True):
        multicrop_scores = compute_multicrop_consistency_scores(
            rows=rows,
            runtime=runtime,
            cfg=dict(filter_cfg.get("multicrop", {})),
        )

    ood_cfg = dict(filter_cfg.get("anchor_ood", {}))
    if stages_enabled.get("anchor_ood", True):
        ood_state = fit_anchor_ood_stats(
            rows=rows,
            image_embeddings=embeddings,
            cfg=ood_cfg,
        )
        ood_scores = compute_anchor_ood_scores(
            rows=rows,
            image_embeddings=embeddings,
            ood_state=ood_state,
        )
    else:
        ood_state = {
            "enabled": False,
            "reason": "disabled_by_stage_config",
            "anchor_count": 0,
            "threshold_md2": 0.0,
            "threshold_quantile": float(ood_cfg.get("threshold_quantile", 0.99)),
        }

    if stages_enabled.get("dedup", True):
        dup_scores = compute_duplicate_similarity(
            rows=rows,
            image_embeddings=embeddings,
            synthetic_only=dedup_synthetic_only,
        )
    if stages_enabled.get("quality", True):
        quality_scores = compute_quality_scores(rows=rows, cfg=dict(filter_cfg.get("quality", {})))

    if bool(phase1_cfg.get("enabled", False)):
        paired_scores, phase1_pair_state = compute_paired_anchor_semantic_scores(
            rows=rows,
            image_embeddings=embeddings,
            cfg=phase1_cfg,
        )
    else:
        phase1_pair_state = {"enabled": False, "pair_hit_count": 0, "pair_miss_count": 0}
    phase1_scores, phase1_state = build_phase1_semantic_scores(
        rows=rows,
        semantic_scores=semantic_scores,
        paired_scores=paired_scores,
        prompt_scores=prompt_scores,
        phase1_cfg=phase1_cfg,
    )

    policy_cfg = dict(filter_cfg.get("policy", {}))
    strategy = str(policy_cfg.get("decision", filter_cfg.get("strategy", "weighted"))).strip().lower()
    calibration_sources = [str(x) for x in policy_cfg.get("calibration_sources", ["real"])]
    calib_rows = [row for row in rows if str(row.get("source", "")) in set(calibration_sources)]
    if not calib_rows:
        calib_rows = rows

    def metric_value(metric_name: str, row: Dict[str, Any]) -> float:
        sid = str(row.get("sample_id", ""))
        if metric_name == "s_prompt":
            return float(prompt_scores.get(sid, 0.0))
        if metric_name == "s_semantic_anchor_raw":
            return float(semantic_scores.get(sid, {}).get("s_semantic_anchor_raw", 0.0))
        if metric_name == "s_semantic_anchor":
            return float(semantic_scores.get(sid, {}).get("s_semantic_anchor", 0.0))
        if metric_name == "s_semantic_pair":
            return float(paired_scores.get(sid, {}).get("s_semantic_pair", 0.0))
        if metric_name == "s_phase1_semantic":
            return float(phase1_scores.get(sid, {}).get("s_phase1_semantic", 0.0))
        if metric_name == "s_prompt_margin":
            return float(prompt_margin_scores.get(sid, {}).get("s_prompt_margin", 0.0))
        if metric_name == "s_prompt_margin_norm":
            return float(prompt_margin_scores.get(sid, {}).get("s_prompt_margin_norm", 0.0))
        if metric_name == "s_consistency":
            return float(cons_scores.get(sid, {}).get("s_consistency", 0.0))
        if metric_name == "s_multicrop_consistency":
            return float(multicrop_scores.get(sid, {}).get("s_multicrop_consistency", 0.0))
        if metric_name == "ood_md2":
            return float(ood_scores.get(sid, {}).get("ood_md2", 0.0))
        if metric_name == "ood_score":
            return float(ood_scores.get(sid, {}).get("ood_score", 1.0))
        if metric_name == "dup_sim":
            return float(dup_scores.get(sid, 0.0))
        if metric_name == "dedup_good":
            return max(0.0, 1.0 - max(0.0, min(1.0, float(dup_scores.get(sid, 0.0)))))
        if metric_name == "blur_norm":
            return float(quality_scores.get(sid, {}).get("blur_norm", 0.0))
        if metric_name == "exposure_score":
            return float(quality_scores.get(sid, {}).get("exposure_score", 0.0))
        return 0.0

    gates_cfg = policy_cfg.get("gates", [])
    if not gates_cfg and strategy in {"tri_gate", "tri_gate_plus_weighted"}:
        tri_cfg = dict(filter_cfg.get("tri_gate", {}))
        clip_vals = [metric_value("s_prompt_margin", row) for row in calib_rows]
        cons_vals = [metric_value("s_multicrop_consistency", row) for row in calib_rows]
        ood_vals = [metric_value("ood_md2", row) for row in calib_rows]
        clip_t = float(tri_cfg.get("clip_margin_threshold", quantile(clip_vals, float(tri_cfg.get("clip_margin_q", 0.05)))))
        cons_t = float(tri_cfg.get("multicrop_threshold", quantile(cons_vals, float(tri_cfg.get("multicrop_q", 0.05)))))
        if ood_state.get("enabled", False):
            default_ood = float(ood_state.get("threshold_md2", quantile(ood_vals, float(tri_cfg.get("ood_q", 0.99)))))
        else:
            default_ood = quantile(ood_vals, float(tri_cfg.get("ood_q", 0.99)))
        ood_t = float(tri_cfg.get("ood_threshold_md2", default_ood))
        gates_cfg = [
            {"metric": "s_prompt_margin", "op": ">=", "threshold": clip_t, "buffer": float(tri_cfg.get("clip_margin_buffer", 0.02))},
            {"metric": "s_multicrop_consistency", "op": ">=", "threshold": cons_t, "buffer": float(tri_cfg.get("multicrop_buffer", 0.02))},
            {"metric": "ood_md2", "op": "<=", "threshold": ood_t, "buffer": float(tri_cfg.get("ood_buffer", 1.0))},
        ]

    weighted_cfg = dict(policy_cfg.get("weighted", {}))
    final_weight_map = dict(weighted_cfg.get("final_score", default_weighted))
    if strategy == "tri_gate":
        final_weight_map = weighted_cfg.get(
            "final_score",
            {
                "s_prompt_margin_norm": 0.40,
                "s_multicrop_consistency": 0.35,
                "ood_score": 0.25,
            },
        )

    gate_specs: List[Dict[str, Any]] = []
    if strategy in {"tri_gate", "tri_gate_plus_weighted"} and isinstance(gates_cfg, list):
        for g in gates_cfg:
            if not isinstance(g, dict):
                continue
            metric_name = str(g.get("metric", "")).strip()
            if not metric_name:
                continue
            op = _as_op(str(g.get("op", ">=")))
            threshold = _resolve_gate_threshold(g, metric_name, calib_rows, metric_value)
            gate_specs.append(
                {
                    "metric": metric_name,
                    "op": op,
                    "threshold": float(threshold),
                    "buffer": float(g.get("buffer", 0.0)),
                    "sources": [str(x).strip() for x in g.get("sources", []) if str(x).strip()],
                    "sources_exclude": [str(x).strip() for x in g.get("sources_exclude", []) if str(x).strip()],
                    "phase1_sources": [str(x).strip() for x in g.get("phase1_sources", []) if str(x).strip()],
                    "phase1_sources_exclude": [
                        str(x).strip() for x in g.get("phase1_sources_exclude", []) if str(x).strip()
                    ],
                }
            )

    score_rows: List[Dict[str, Any]] = []
    phase1_compare_rows: List[Dict[str, Any]] = []
    for row in rows:
        sample_id = str(row.get("sample_id", "unknown"))
        source = str(row.get("source", ""))
        s_prompt = metric_value("s_prompt", row)
        s_semantic_anchor_raw = metric_value("s_semantic_anchor_raw", row)
        s_semantic_anchor = metric_value("s_semantic_anchor", row)
        s_semantic_pair = metric_value("s_semantic_pair", row)
        s_phase1_semantic = metric_value("s_phase1_semantic", row)
        s_phase1_semantic_source = str(phase1_scores.get(sample_id, {}).get("s_phase1_semantic_source", ""))
        s_prompt_margin = metric_value("s_prompt_margin", row)
        s_prompt_margin_norm = metric_value("s_prompt_margin_norm", row)
        s_consistency = metric_value("s_consistency", row)
        s_multicrop = metric_value("s_multicrop_consistency", row)
        ood_md2 = metric_value("ood_md2", row)
        ood_score = metric_value("ood_score", row)
        dup_sim = metric_value("dup_sim", row)
        dedup_good = metric_value("dedup_good", row)
        blur_score = float(quality_scores.get(sample_id, {}).get("blur_score", 0.0))
        blur_norm = metric_value("blur_norm", row)
        exposure_score = metric_value("exposure_score", row)
        pm = prompt_margin_scores.get(sample_id, {})
        cons = cons_scores.get(sample_id, {})
        mcons = multicrop_scores.get(sample_id, {})

        final_score = 0.0
        for metric_name, weight in final_weight_map.items():
            final_score += float(weight) * metric_value(str(metric_name), row)
        final_score = max(0.0, min(1.0, final_score))

        decision_basis = "weighted_policy"
        gate_fail = ""
        gate_checks: List[str] = []
        if strategy in {"tri_gate", "tri_gate_plus_weighted"} and gate_specs:
            all_pass = True
            near = False
            applied_gate_count = 0
            gate_fail_reasons: List[str] = []
            for g in gate_specs:
                metric_name = str(g["metric"])
                op = str(g["op"])
                threshold = float(g["threshold"])
                if not _gate_applies_to_row(gate_cfg=g, row=row, phase1_source=s_phase1_semantic_source):
                    gate_checks.append(f"{metric_name} skip (gate condition not matched)")
                    continue
                applied_gate_count += 1
                mv = metric_value(metric_name, row)
                passed = _eval_gate(mv, op, threshold)
                gate_checks.append(f"{metric_name} {mv:.6f} {op} {threshold:.6f} => {'pass' if passed else 'fail'}")
                if not passed:
                    all_pass = False
                    gate_fail_reasons.append(metric_name)
                    buf = float(g["buffer"])
                    if op in {">=", ">"}:
                        near = near or (mv >= threshold - buf)
                    elif op in {"<=", "<"}:
                        near = near or (mv <= threshold + buf)
                    else:
                        near = near or (abs(mv - threshold) <= buf)

            if applied_gate_count == 0:
                decision = choose_decision(final_score, accept_threshold, uncertain_low, uncertain_high)
            elif all_pass:
                decision = "accept"
            elif near:
                decision = "uncertain"
            else:
                decision = "reject"
            gate_fail = ",".join(gate_fail_reasons)
            decision_basis = "policy_tri_gate"
        else:
            decision = choose_decision(final_score, accept_threshold, uncertain_low, uncertain_high)

        keep = decision == "accept"
        if keep_real_always and source == "real":
            decision = "accept"
            keep = True
            final_score = 1.0
            if strategy in {"tri_gate", "tri_gate_plus_weighted"}:
                decision_basis = "policy_tri_gate_keep_real_always"
            else:
                decision_basis = "keep_real_always"
            gate_fail = ""

        active_prompt_text = _resolve_row_prompt_text(row=row, prompt_field=prompt_field, default_prompt=prompt_text)
        pair_info = paired_scores.get(sample_id, {})
        pair_anchor_sid = str(pair_info.get("anchor_sid_resolved", "")).strip()
        pair_miss_reason = str(pair_info.get("pair_miss_reason", "")).strip()
        if s_phase1_semantic_source.startswith("semantic_pair"):
            compare_type = "image_vs_anchor_image"
            compare_target = pair_anchor_sid
            compare_remark = "guided synthetic matched anchor"
            if s_phase1_semantic_source == "semantic_pair_fused":
                compare_remark = "guided synthetic fused anchor+prompt score"
        elif s_phase1_semantic_source == "prompt_score":
            compare_type = "image_vs_prompt_text"
            compare_target = "effective_prompt_text"
            compare_remark = "prompt-only synthetic routed to prompt score"
        else:
            compare_type = "image_vs_real_anchor_set"
            compare_target = "real_anchor_pool"
            compare_remark = "fallback to semantic anchor"
            if pair_miss_reason:
                compare_remark = f"{compare_remark}; {pair_miss_reason}"

        phase1_compare_rows.append(
            {
                "sample_id": sample_id,
                "source": source,
                "decision": decision,
                "phase1_source": s_phase1_semantic_source,
                "phase1_score": round(s_phase1_semantic, 6),
                "compare_type": compare_type,
                "compare_target": compare_target,
                "anchor_real_sample_id": pair_anchor_sid or str(row.get("anchor_real_sample_id", "")),
                "pair_hit": float(pair_info.get("s_semantic_pair_hit", 0.0)),
                "pair_miss_reason": pair_miss_reason,
                "s_semantic_pair": round(s_semantic_pair, 6),
                "s_prompt": round(s_prompt, 6),
                "s_semantic_anchor": round(s_semantic_anchor, 6),
                "prompt_text_used": active_prompt_text,
                "gate_fail": gate_fail,
                "gate_checks": gate_checks,
                "remark": compare_remark,
            }
        )

        score_rows.append(
            {
                "image_id": sample_id,
                "sample_id": sample_id,
                "source": source,
                "s_prompt": round(s_prompt, 6),
                "s_semantic_anchor_raw": round(s_semantic_anchor_raw, 6),
                "s_semantic_anchor": round(s_semantic_anchor, 6),
                "s_semantic_pair": round(s_semantic_pair, 6),
                "s_phase1_semantic": round(s_phase1_semantic, 6),
                "s_phase1_semantic_source": s_phase1_semantic_source,
                "s_prompt_margin": round(s_prompt_margin, 6),
                "s_prompt_margin_norm": round(s_prompt_margin_norm, 6),
                "s_prompt_pos": round(float(pm.get("s_prompt_pos", 0.0)), 6),
                "s_prompt_neg_max": round(float(pm.get("s_prompt_neg_max", 0.0)), 6),
                "s_consistency": round(s_consistency, 6),
                "s_multicrop_consistency": round(s_multicrop, 6),
                "multicrop_pair_sim_min": round(float(mcons.get("multicrop_pair_sim_min", 0.0)), 6),
                "multicrop_pair_sim_max": round(float(mcons.get("multicrop_pair_sim_max", 0.0)), 6),
                "multicrop_pair_sim_mean": round(float(mcons.get("multicrop_pair_sim_mean", 0.0)), 6),
                "multicrop_views": int(float(mcons.get("multicrop_views", 0.0))),
                "ood_md2": round(ood_md2, 6),
                "ood_score": round(ood_score, 6),
                "dup_sim": round(dup_sim, 6),
                "blur_score": round(blur_score, 4),
                "final_score": round(final_score, 6),
                "keep": keep,
                "score_asf": round(final_score, 6),
                "score_pcs": round(s_consistency, 6),
                "pcs_similarity_min": round(float(cons.get("pcs_similarity_min", 0.0)), 6),
                "pcs_similarity_max": round(float(cons.get("pcs_similarity_max", 0.0)), 6),
                "pcs_similarity_mean": round(float(cons.get("pcs_similarity_mean", 0.0)), 6),
                "pcs_repeats": int(float(cons.get("pcs_repeats", 0.0))),
                "exposure_score": round(exposure_score, 6),
                "decision": decision,
                "decision_basis": decision_basis,
                "gate_fail": gate_fail,
                "gate_checks": gate_checks,
                "clip_model_id": model_id,
                "clip_device": runtime.device,
            }
        )

    phase1_log_path = filter_dir / "phase1_compare_log.jsonl"
    write_jsonl(phase1_log_path, phase1_compare_rows)

    report_extra: Dict[str, Any] = {
        "clip_model_id": model_id,
        "clip_device": runtime.device,
        "keep_real_always": keep_real_always,
        "strategy": strategy,
        "prompt_text_present": bool(prompt_text.strip()),
        "prompt_text_source": str(clip_cfg.get("prompt_text_source", "")),
        "prompt_score_mode": prompt_score_mode,
        "negative_prompt_count": len(neg_prompts),
        "stages_enabled": stages_enabled,
        "policy": {
            "decision": strategy,
            "calibration_sources": calibration_sources,
            "gates": gates_cfg,
            "weighted_final_score": final_weight_map,
        },
        "semantic_anchor": {
            "enabled": bool(semantic_state.get("enabled", False)),
            "reason": str(semantic_state.get("reason", "")) if not bool(semantic_state.get("enabled", False)) else "",
            "anchor_count": int(semantic_state.get("anchor_count", 0)),
            "reduce": str(semantic_state.get("reduce", semantic_cfg.get("reduce", "median"))),
            "self_exclude_for_real": bool(semantic_state.get("self_exclude_for_real", semantic_cfg.get("self_exclude_for_real", True))),
            "min_anchor_count": int(semantic_state.get("min_anchor_count", semantic_cfg.get("min_anchor_count", 4))),
            "anchor_sem_raw_p50": float(semantic_state.get("anchor_sem_raw_p50", 0.0)),
            "anchor_sem_raw_p95": float(semantic_state.get("anchor_sem_raw_p95", 0.0)),
            "anchor_sem_raw_p99": float(semantic_state.get("anchor_sem_raw_p99", 0.0)),
        },
        "phase1_semantic": {
            **phase1_state,
            "paired": phase1_pair_state,
            "prompt_field": prompt_field,
            "compare_log_path": str(phase1_log_path),
            "compare_log_count": len(phase1_compare_rows),
        },
        "anchor_ood": {
            "enabled": bool(ood_state.get("enabled", False)),
            "reason": str(ood_state.get("reason", "")) if not bool(ood_state.get("enabled", False)) else "",
            "anchor_count": int(ood_state.get("anchor_count", 0)),
            "covariance_type": str(ood_state.get("covariance_type", "")),
            "diag_var_floor": float(ood_state.get("diag_var_floor", ood_cfg.get("diag_var_floor", 1e-3))),
            "threshold_md2": float(ood_state.get("threshold_md2", 0.0)),
            "threshold_quantile": float(ood_state.get("threshold_quantile", ood_cfg.get("threshold_quantile", 0.99))),
            "anchor_md2_p50": float(ood_state.get("anchor_md2_p50", 0.0)),
            "anchor_md2_p95": float(ood_state.get("anchor_md2_p95", 0.0)),
            "anchor_md2_p99": float(ood_state.get("anchor_md2_p99", 0.0)),
        },
        **cache_stats,
    }
    return score_rows, report_extra


def run_staged_clip_filter(
    rows: List[Dict[str, Any]],
    filter_dir: Path,
    accept_threshold: float,
    uncertain_low: float,
    uncertain_high: float,
    filter_cfg: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    clip_cfg = dict(filter_cfg.get("clip", {}))
    model_id = str(
        clip_cfg.get(
            "model_id",
            filter_cfg.get("clip_model_id", "openai/clip-vit-base-patch32"),
        )
    )
    device = str(clip_cfg.get("device", "auto"))
    prompt_text = str(clip_cfg.get("prompt_text", filter_cfg.get("prompt_text", "")))
    prompt_score_mode = _resolve_prompt_score_mode(clip_cfg=clip_cfg, model_id=model_id)
    neg_prompts = [str(x) for x in clip_cfg.get("negative_prompts", [])]
    cache_path = Path(str(clip_cfg.get("embed_cache_path", filter_dir / "clip_embed_cache.json")))
    strategy = str(filter_cfg.get("strategy", "weighted")).strip().lower()
    phase1_cfg = dict(filter_cfg.get("phase1_semantic", {}))

    score_cfg = dict(filter_cfg.get("score", {}))
    w_prompt = float(score_cfg.get("w_prompt", 0.30))
    w_semantic_anchor = float(score_cfg.get("w_semantic_anchor", 0.0))
    w_cons = float(score_cfg.get("w_consistency", 0.35))
    w_multicrop = float(score_cfg.get("w_multicrop", 0.0))
    w_dedup = float(score_cfg.get("w_dedup", 0.20))
    w_blur = float(score_cfg.get("w_blur", 0.10))
    w_exposure = float(score_cfg.get("w_exposure", 0.05))
    w_ood = float(score_cfg.get("w_ood", 0.0))

    dedup_cfg = dict(filter_cfg.get("dedup", {}))
    dedup_synthetic_only = bool(dedup_cfg.get("synthetic_only", False))
    keep_real_always = bool(filter_cfg.get("keep_real_always", True))

    embeddings, runtime, cache_stats = build_image_embeddings(
        rows=rows,
        model_id=model_id,
        device_cfg=device,
        cache_path=cache_path,
    )
    prompt_scores = compute_prompt_scores(
        rows=rows,
        image_embeddings=embeddings,
        runtime=runtime,
        prompt_text=prompt_text,
        prompt_score_mode=prompt_score_mode,
        prompt_field=str(phase1_cfg.get("prompt_field", "effective_prompt_text")),
    )
    prompt_margin_scores = compute_prompt_margin_scores(
        rows=rows,
        image_embeddings=embeddings,
        runtime=runtime,
        pos_prompt=prompt_text,
        neg_prompts=neg_prompts,
        prompt_score_mode=prompt_score_mode,
    )
    semantic_cfg = dict(filter_cfg.get("semantic_anchor", {}))
    semantic_scores, semantic_state = compute_anchor_semantic_scores(
        rows=rows,
        image_embeddings=embeddings,
        cfg=semantic_cfg,
    )
    if bool(phase1_cfg.get("enabled", False)):
        paired_scores, phase1_pair_state = compute_paired_anchor_semantic_scores(
            rows=rows,
            image_embeddings=embeddings,
            cfg=phase1_cfg,
        )
    else:
        paired_scores = {
            str(r.get("sample_id", "")): {
                "s_semantic_pair_raw": 0.0,
                "s_semantic_pair": 0.0,
                "s_semantic_pair_hit": 0.0,
            }
            for r in rows
        }
        phase1_pair_state = {"enabled": False, "pair_hit_count": 0, "pair_miss_count": 0}
    phase1_scores, phase1_state = build_phase1_semantic_scores(
        rows=rows,
        semantic_scores=semantic_scores,
        paired_scores=paired_scores,
        prompt_scores=prompt_scores,
        phase1_cfg=phase1_cfg,
    )
    cons_scores = compute_consistency_scores(
        rows=rows,
        image_embeddings=embeddings,
        runtime=runtime,
        cfg=dict(filter_cfg.get("pcs", {})),
        work_dir=filter_dir,
    )
    multicrop_scores = compute_multicrop_consistency_scores(
        rows=rows,
        runtime=runtime,
        cfg=dict(filter_cfg.get("multicrop", {})),
    )
    ood_cfg = dict(filter_cfg.get("anchor_ood", {}))
    ood_state = fit_anchor_ood_stats(
        rows=rows,
        image_embeddings=embeddings,
        cfg=ood_cfg,
    )
    ood_scores = compute_anchor_ood_scores(
        rows=rows,
        image_embeddings=embeddings,
        ood_state=ood_state,
    )
    dup_scores = compute_duplicate_similarity(
        rows=rows,
        image_embeddings=embeddings,
        synthetic_only=dedup_synthetic_only,
    )
    quality_scores = compute_quality_scores(rows=rows, cfg=dict(filter_cfg.get("quality", {})))

    tri_cfg = dict(filter_cfg.get("tri_gate", {}))
    tri_clip_q = float(tri_cfg.get("clip_margin_q", 0.05))
    tri_cons_q = float(tri_cfg.get("multicrop_q", 0.05))
    tri_ood_q = float(tri_cfg.get("ood_q", 0.99))
    tri_clip_buf = float(tri_cfg.get("clip_margin_buffer", 0.02))
    tri_cons_buf = float(tri_cfg.get("multicrop_buffer", 0.02))
    tri_ood_buf = float(tri_cfg.get("ood_buffer", 1.0))
    tri_keep_real_always = bool(tri_cfg.get("keep_real_always", keep_real_always))

    calib_sources = [str(x) for x in tri_cfg.get("calibration_sources", ["real"])]
    calib_rows = [row for row in rows if str(row.get("source", "")) in set(calib_sources)]
    if not calib_rows:
        calib_rows = rows
    calib_ids = [str(row.get("sample_id", "")) for row in calib_rows]

    clip_vals = [float(prompt_margin_scores.get(sid, {}).get("s_prompt_margin", 0.0)) for sid in calib_ids]
    cons_vals = [float(multicrop_scores.get(sid, {}).get("s_multicrop_consistency", 0.0)) for sid in calib_ids]
    ood_vals = [float(ood_scores.get(sid, {}).get("ood_md2", 0.0)) for sid in calib_ids]

    tri_clip_t = float(tri_cfg.get("clip_margin_threshold", quantile(clip_vals, tri_clip_q)))
    tri_cons_t = float(tri_cfg.get("multicrop_threshold", quantile(cons_vals, tri_cons_q)))
    if ood_state.get("enabled", False):
        default_ood = float(ood_state.get("threshold_md2", quantile(ood_vals, tri_ood_q)))
    else:
        default_ood = quantile(ood_vals, tri_ood_q)
    tri_ood_t = float(tri_cfg.get("ood_threshold_md2", default_ood))

    score_rows: List[Dict[str, Any]] = []
    for row in rows:
        sample_id = str(row.get("sample_id", "unknown"))
        source = str(row.get("source", ""))
        s_prompt = float(prompt_scores.get(sample_id, 0.0))
        sem = semantic_scores.get(sample_id, {})
        s_semantic_anchor_raw = float(sem.get("s_semantic_anchor_raw", 0.0))
        s_semantic_anchor = float(sem.get("s_semantic_anchor", 0.0))
        s_semantic_pair = float(paired_scores.get(sample_id, {}).get("s_semantic_pair", 0.0))
        s_phase1_semantic = float(phase1_scores.get(sample_id, {}).get("s_phase1_semantic", 0.0))
        s_phase1_semantic_source = str(phase1_scores.get(sample_id, {}).get("s_phase1_semantic_source", ""))
        pm = prompt_margin_scores.get(sample_id, {})
        s_prompt_margin = float(pm.get("s_prompt_margin", 0.0))
        s_prompt_margin_norm = float(pm.get("s_prompt_margin_norm", 0.0))
        cons = cons_scores.get(sample_id, {})
        s_consistency = float(cons.get("s_consistency", 0.0))
        mcons = multicrop_scores.get(sample_id, {})
        s_multicrop = float(mcons.get("s_multicrop_consistency", 0.0))
        ood = ood_scores.get(sample_id, {})
        ood_md2 = float(ood.get("ood_md2", 0.0))
        ood_score = float(ood.get("ood_score", 1.0))
        dup_sim = float(dup_scores.get(sample_id, 0.0))
        q = quality_scores.get(sample_id, {})
        blur_score = float(q.get("blur_score", 0.0))
        blur_norm = float(q.get("blur_norm", 0.0))
        exposure_score = float(q.get("exposure_score", 0.0))

        # Lower duplicate similarity is better for diversity.
        dedup_good = max(0.0, 1.0 - max(0.0, min(1.0, dup_sim)))
        if strategy == "tri_gate":
            clip_pass = s_prompt_margin >= tri_clip_t
            cons_pass = s_multicrop >= tri_cons_t
            ood_pass = ood_md2 <= tri_ood_t
            all_pass = clip_pass and cons_pass and ood_pass

            clip_near = (tri_clip_t - tri_clip_buf) <= s_prompt_margin < tri_clip_t
            cons_near = (tri_cons_t - tri_cons_buf) <= s_multicrop < tri_cons_t
            ood_near = tri_ood_t < ood_md2 <= (tri_ood_t + tri_ood_buf)

            if all_pass:
                decision = "accept"
            elif clip_near or cons_near or ood_near:
                decision = "uncertain"
            else:
                decision = "reject"

            final_score = (
                0.40 * s_prompt_margin_norm
                + 0.35 * s_multicrop
                + 0.25 * ood_score
            )
            final_score = max(0.0, min(1.0, final_score))
            keep = decision == "accept"
            decision_basis = "tri_gate"
            gate_fail_reasons = []
            if not clip_pass:
                gate_fail_reasons.append("clip_margin")
            if not cons_pass:
                gate_fail_reasons.append("multicrop_consistency")
            if not ood_pass:
                gate_fail_reasons.append("anchor_ood")
            gate_fail = ",".join(gate_fail_reasons)

            if tri_keep_real_always and source == "real":
                decision = "accept"
                keep = True
                final_score = 1.0
                decision_basis = "tri_gate_keep_real_always"
                gate_fail = ""
        else:
            final_score = (
                w_prompt * s_prompt
                + w_semantic_anchor * s_semantic_anchor
                + w_cons * s_consistency
                + w_multicrop * s_multicrop
                + w_dedup * dedup_good
                + w_blur * blur_norm
                + w_exposure * exposure_score
                + w_ood * ood_score
            )
            final_score = max(0.0, min(1.0, final_score))
            decision = choose_decision(final_score, accept_threshold, uncertain_low, uncertain_high)
            decision_basis = "weighted_stage_score"
            keep = decision == "accept"
            gate_fail = ""

            # Real-anchor protection: by default never drop real rows in staged mode.
            if keep_real_always and source == "real":
                final_score = 1.0
                decision = "accept"
                keep = True
                decision_basis = "keep_real_always"

        score_rows.append(
            {
                "image_id": sample_id,
                "sample_id": sample_id,
                "source": source,
                "s_prompt": round(s_prompt, 6),
                "s_semantic_anchor_raw": round(s_semantic_anchor_raw, 6),
                "s_semantic_anchor": round(s_semantic_anchor, 6),
                "s_semantic_pair": round(s_semantic_pair, 6),
                "s_phase1_semantic": round(s_phase1_semantic, 6),
                "s_phase1_semantic_source": s_phase1_semantic_source,
                "s_prompt_margin": round(s_prompt_margin, 6),
                "s_prompt_margin_norm": round(s_prompt_margin_norm, 6),
                "s_prompt_pos": round(float(pm.get("s_prompt_pos", 0.0)), 6),
                "s_prompt_neg_max": round(float(pm.get("s_prompt_neg_max", 0.0)), 6),
                "s_consistency": round(s_consistency, 6),
                "s_multicrop_consistency": round(s_multicrop, 6),
                "multicrop_pair_sim_min": round(float(mcons.get("multicrop_pair_sim_min", 0.0)), 6),
                "multicrop_pair_sim_max": round(float(mcons.get("multicrop_pair_sim_max", 0.0)), 6),
                "multicrop_pair_sim_mean": round(float(mcons.get("multicrop_pair_sim_mean", 0.0)), 6),
                "multicrop_views": int(float(mcons.get("multicrop_views", 0.0))),
                "ood_md2": round(ood_md2, 6),
                "ood_score": round(ood_score, 6),
                "dup_sim": round(dup_sim, 6),
                "blur_score": round(blur_score, 4),
                "final_score": round(final_score, 6),
                "keep": keep,
                "score_asf": round(final_score, 6),
                "score_pcs": round(s_consistency, 6),
                "pcs_similarity_min": round(float(cons.get("pcs_similarity_min", 0.0)), 6),
                "pcs_similarity_max": round(float(cons.get("pcs_similarity_max", 0.0)), 6),
                "pcs_similarity_mean": round(float(cons.get("pcs_similarity_mean", 0.0)), 6),
                "pcs_repeats": int(float(cons.get("pcs_repeats", 0.0))),
                "exposure_score": round(exposure_score, 6),
                "decision": decision,
                "decision_basis": decision_basis,
                "gate_fail": gate_fail,
                "clip_model_id": model_id,
                "clip_device": runtime.device,
            }
        )

    report_extra: Dict[str, Any] = {
        "weights": {
            "w_prompt": w_prompt,
            "w_semantic_anchor": w_semantic_anchor,
            "w_consistency": w_cons,
            "w_multicrop": w_multicrop,
            "w_dedup": w_dedup,
            "w_blur": w_blur,
            "w_exposure": w_exposure,
            "w_ood": w_ood,
        },
        "clip_model_id": model_id,
        "clip_device": runtime.device,
        "keep_real_always": keep_real_always,
        "strategy": strategy,
        "prompt_text_present": bool(prompt_text.strip()),
        "prompt_text_source": str(clip_cfg.get("prompt_text_source", "")),
        "prompt_score_mode": prompt_score_mode,
        "negative_prompt_count": len(neg_prompts),
        "tri_gate": {
            "calibration_sources": calib_sources,
            "clip_margin_threshold": tri_clip_t,
            "multicrop_threshold": tri_cons_t,
            "ood_threshold_md2": tri_ood_t,
            "clip_margin_q": tri_clip_q,
            "multicrop_q": tri_cons_q,
            "ood_q": tri_ood_q,
            "clip_margin_buffer": tri_clip_buf,
            "multicrop_buffer": tri_cons_buf,
            "ood_buffer": tri_ood_buf,
            "keep_real_always": tri_keep_real_always,
        },
        "semantic_anchor": {
            "enabled": bool(semantic_state.get("enabled", False)),
            "reason": str(semantic_state.get("reason", "")) if not bool(semantic_state.get("enabled", False)) else "",
            "anchor_count": int(semantic_state.get("anchor_count", 0)),
            "reduce": str(semantic_state.get("reduce", semantic_cfg.get("reduce", "median"))),
            "self_exclude_for_real": bool(semantic_state.get("self_exclude_for_real", semantic_cfg.get("self_exclude_for_real", True))),
            "min_anchor_count": int(semantic_state.get("min_anchor_count", semantic_cfg.get("min_anchor_count", 4))),
            "anchor_sem_raw_p50": float(semantic_state.get("anchor_sem_raw_p50", 0.0)),
            "anchor_sem_raw_p95": float(semantic_state.get("anchor_sem_raw_p95", 0.0)),
            "anchor_sem_raw_p99": float(semantic_state.get("anchor_sem_raw_p99", 0.0)),
        },
        "phase1_semantic": {
            **phase1_state,
            "paired": phase1_pair_state,
            "prompt_field": str(phase1_cfg.get("prompt_field", "effective_prompt_text")),
        },
        "anchor_ood": {
            "enabled": bool(ood_state.get("enabled", False)),
            "reason": str(ood_state.get("reason", "")) if not bool(ood_state.get("enabled", False)) else "",
            "anchor_count": int(ood_state.get("anchor_count", 0)),
            "covariance_type": str(ood_state.get("covariance_type", "")),
            "diag_var_floor": float(ood_state.get("diag_var_floor", ood_cfg.get("diag_var_floor", 1e-3))),
            "threshold_md2": float(ood_state.get("threshold_md2", tri_ood_t)) if bool(ood_state.get("enabled", False)) else tri_ood_t,
            "threshold_quantile": float(ood_state.get("threshold_quantile", ood_cfg.get("threshold_quantile", 0.99))),
            "anchor_md2_p50": float(ood_state.get("anchor_md2_p50", 0.0)),
            "anchor_md2_p95": float(ood_state.get("anchor_md2_p95", 0.0)),
            "anchor_md2_p99": float(ood_state.get("anchor_md2_p99", 0.0)),
        },
        **cache_stats,
    }
    return score_rows, report_extra


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter stage with stub / pcs_clip / staged_clip / compose modes")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_config(config_path)
    run_dir = resolve_run_dir(config)
    filter_cfg = config.get("filter", {})
    if isinstance(filter_cfg, dict):
        prompt_source = _resolve_filter_prompt_text(filter_cfg=filter_cfg, config_path=config_path)
        clip_cfg = filter_cfg.get("clip")
        if prompt_source and isinstance(clip_cfg, dict):
            clip_cfg["prompt_text_source"] = prompt_source

    input_manifest_path, input_manifest_source = _resolve_filter_input_manifest(
        filter_cfg=filter_cfg,
        run_dir=run_dir,
    )
    builder_cfg = dict(filter_cfg.get("manifest_builder", {}))
    builder_enabled = bool(builder_cfg.get("enabled", False))
    builder_force = bool(builder_cfg.get("force_rebuild", False))

    if builder_enabled and (builder_force or input_manifest_path is None or not input_manifest_path.exists()):
        rows = build_input_manifest_from_config(filter_cfg=filter_cfg, input_manifest_path=input_manifest_path)
        if not input_manifest_source:
            input_manifest_source = "filter.manifest_builder"
    elif input_manifest_path is not None:
        rows = read_jsonl(input_manifest_path)
    else:
        rows = build_stub_manifest(
            total_count=int(filter_cfg.get("stub_total_count", 24)),
            real_ratio=float(filter_cfg.get("stub_real_ratio", 0.5)),
        )
        input_manifest_source = "stub_manifest"

    accept_threshold = float(filter_cfg.get("accept_threshold", 0.6))
    uncertain_low = float(filter_cfg.get("uncertain_low", 0.45))
    uncertain_high = float(filter_cfg.get("uncertain_high", accept_threshold))
    mode = str(filter_cfg.get("mode", "stub"))

    filter_dir = run_dir / "filter"
    splits_dir = filter_dir / "splits"
    filter_dir.mkdir(parents=True, exist_ok=True)
    splits_dir.mkdir(parents=True, exist_ok=True)

    report_extra: Dict[str, Any] = {}
    if mode == "stub":
        score_rows = run_stub_filter(rows, accept_threshold, uncertain_low, uncertain_high)
    elif mode == "pcs_clip":
        score_rows = run_pcs_clip_filter(
            rows=rows,
            filter_dir=filter_dir,
            accept_threshold=accept_threshold,
            uncertain_low=uncertain_low,
            uncertain_high=uncertain_high,
            filter_cfg=filter_cfg,
        )
    elif mode == "staged_clip":
        score_rows, report_extra = run_staged_clip_filter(
            rows=rows,
            filter_dir=filter_dir,
            accept_threshold=accept_threshold,
            uncertain_low=uncertain_low,
            uncertain_high=uncertain_high,
            filter_cfg=filter_cfg,
        )
    elif mode == "compose":
        score_rows, report_extra = run_composed_clip_filter(
            rows=rows,
            filter_dir=filter_dir,
            accept_threshold=accept_threshold,
            uncertain_low=uncertain_low,
            uncertain_high=uncertain_high,
            filter_cfg=filter_cfg,
        )
    else:
        raise ValueError(f"unsupported filter.mode: {mode}")

    ranking_state = _apply_topk_review_selection(score_rows=score_rows, filter_cfg=filter_cfg)
    if bool(ranking_state.get("enabled", False)):
        report_extra = dict(report_extra)
        report_extra["ranking_review"] = ranking_state
        _annotate_phase1_compare_log_with_final_decision(report_extra=report_extra, score_rows=score_rows)

    accept_set = {r["sample_id"] for r in score_rows if r.get("decision") == "accept"}
    reject_set = {r["sample_id"] for r in score_rows if r.get("decision") == "reject"}
    uncertain_set = {r["sample_id"] for r in score_rows if r.get("decision") == "uncertain"}

    accept_rows = [row for row in rows if str(row.get("sample_id", "")) in accept_set]
    reject_rows = [row for row in rows if str(row.get("sample_id", "")) in reject_set]
    uncertain_rows = [row for row in rows if str(row.get("sample_id", "")) in uncertain_set]

    write_jsonl(filter_dir / "manifest_in.jsonl", rows)
    write_jsonl(filter_dir / "filter_scores.jsonl", score_rows)
    write_jsonl(splits_dir / "accept.jsonl", accept_rows)
    write_jsonl(splits_dir / "reject.jsonl", reject_rows)
    write_jsonl(splits_dir / "uncertain.jsonl", uncertain_rows)

    report = {
        "stage": "filter",
        "mode": mode,
        "run_dir": str(run_dir),
        "input_manifest_path": str(input_manifest_path) if input_manifest_path is not None else "",
        "input_manifest_source": input_manifest_source,
        "total": len(rows),
        "accept": len(accept_rows),
        "reject": len(reject_rows),
        "uncertain": len(uncertain_rows),
        "accept_ratio": round(len(accept_rows) / len(rows), 4) if rows else 0.0,
        "thresholds": {
            "accept_threshold": accept_threshold,
            "uncertain_low": uncertain_low,
            "uncertain_high": uncertain_high,
        },
        **report_extra,
    }
    write_json(filter_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
