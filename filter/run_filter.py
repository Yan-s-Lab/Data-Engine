#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_io import load_config, resolve_run_dir
from common.manifest_io import read_jsonl, write_json, write_jsonl
from filter.filter_stages import (
    compute_paired_anchor_semantic_scores,
    build_image_embeddings,
    compute_prompt_margin_scores,
    compute_prompt_scores,
)
from filter.manifest_builder import build_input_manifest_from_config


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
    rank_metric = str(ranking_cfg.get("rank_metric", "s_final")).strip()
    keep_top_k = int(ranking_cfg.get("keep_top_k", 0))
    keep_top_ratio = float(ranking_cfg.get("keep_top_ratio", 0.0))
    review_rest = bool(ranking_cfg.get("review_rest", True))
    guided_min_anchor = float(ranking_cfg.get("guided_min_anchor", 0.0))
    guided_min_prompt = float(ranking_cfg.get("guided_min_prompt", 0.0))
    guided_min_prompt_from_real_quantile = str(ranking_cfg.get("guided_min_prompt_from_real_quantile", "")).strip().lower()
    hard_reject = bool(ranking_cfg.get("hard_reject", False))

    if guided_min_prompt_from_real_quantile:
        real_scores = sorted(
            float(r.get("s_prompt", 0.0))
            for r in score_rows
            if str(r.get("source", "")) == "real"
        )
        if real_scores:
            q_map = {
                "q05": 0.05,
                "q10": 0.10,
                "q25": 0.25,
                "q50": 0.50,
                "q75": 0.75,
                "q90": 0.90,
                "q95": 0.95,
            }
            q = q_map.get(guided_min_prompt_from_real_quantile)
            if q is not None:
                idx = int(round((len(real_scores) - 1) * q))
                idx = max(0, min(len(real_scores) - 1, idx))
                guided_min_prompt = float(real_scores[idx])

    candidates = [r for r in score_rows if str(r.get("source", "")) == target_source]
    total = len(candidates)
    eligible_rows: List[Dict[str, Any]] = []
    ineligible_rows: List[Dict[str, Any]] = []
    for row in candidates:
        route = str(row.get("phase1_route", "")).strip()
        s_anchor = float(row.get("s_anchor", 0.0))
        s_prompt = float(row.get("s_prompt", 0.0))
        if route == "guided":
            ok = (s_anchor >= guided_min_anchor) and (s_prompt > guided_min_prompt)
        else:
            ok = True
        if ok:
            eligible_rows.append(row)
        else:
            ineligible_rows.append(row)
    eligible_rows = sorted(eligible_rows, key=lambda r: float(r.get(rank_metric, 0.0)), reverse=True)

    keep_n = 0
    eligible_total = len(eligible_rows)
    if keep_top_k > 0:
        keep_n = min(eligible_total, keep_top_k)
    elif keep_top_ratio > 0.0:
        keep_n = min(eligible_total, max(0, int(round(eligible_total * keep_top_ratio))))

    keep_ids = {str(r.get("sample_id", "")) for r in eligible_rows[:keep_n]}
    eligible_ids = {str(r.get("sample_id", "")) for r in eligible_rows}
    rank_map = {str(r.get("sample_id", "")): idx + 1 for idx, r in enumerate(eligible_rows)}

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
            row["decision_basis"] = "phase1_v1_topk_keep"
            accept_count += 1
        else:
            row["decision"] = "reject" if hard_reject else ("uncertain" if review_rest else "accept")
            row["keep"] = False
            if sid not in eligible_ids:
                row["decision_basis"] = "phase1_v1_ineligible_reject" if hard_reject else "phase1_v1_ineligible_review"
            else:
                row["decision_basis"] = "phase1_v1_review_queue" if not hard_reject else "phase1_v1_topk_reject"
            if row["decision"] == "uncertain":
                uncertain_count += 1
            elif row["decision"] == "reject":
                reject_count += 1
            else:
                accept_count += 1

    return {
        "enabled": True,
        "target_source": target_source,
        "rank_metric": rank_metric,
        "candidate_total": total,
        "eligible_total": eligible_total,
        "keep_top_k": keep_top_k,
        "keep_top_ratio": keep_top_ratio,
        "keep_count": keep_n,
        "review_rest": review_rest,
        "guided_min_anchor": guided_min_anchor,
        "guided_min_prompt": guided_min_prompt,
        "guided_min_prompt_from_real_quantile": guided_min_prompt_from_real_quantile,
        "hard_reject": hard_reject,
        "ineligible_count": len(ineligible_rows),
        "accept_after_selection": accept_count,
        "uncertain_after_selection": uncertain_count,
        "reject_after_selection": reject_count,
    }


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
                "s_anchor": 0.0,
                "s_prompt": float(prompt_scores.get(sid, 0.0)),
                "s_final": float(prompt_scores.get(sid, 0.0)),
                "w_anchor": 0.0,
                "w_prompt": 1.0,
                "phase1_route": "prompt_only",
            }
        return out_disabled, {"enabled": False}

    guided_w_anchor = float(phase1_cfg.get("guided_w_anchor", 0.8))
    guided_w_prompt = float(phase1_cfg.get("guided_w_prompt", 0.2))
    guided_w_sum = guided_w_anchor + guided_w_prompt
    if guided_w_sum <= 0.0:
        guided_w_anchor = 1.0
        guided_w_prompt = 0.0
    else:
        guided_w_anchor = guided_w_anchor / guided_w_sum
        guided_w_prompt = guided_w_prompt / guided_w_sum

    out: Dict[str, Dict[str, Any]] = {}
    guided_count = 0
    prompt_only_count = 0
    anchor_hit_count = 0
    prompt_metric = str(phase1_cfg.get("prompt_metric", "score")).strip().lower()

    for row in rows:
        sid = str(row.get("sample_id", ""))
        is_guided = _is_real_guided_synth(row=row, phase1_cfg=phase1_cfg)
        prompt_raw = float(prompt_scores.get(sid, 0.0))
        if prompt_metric in {"raw_cosine", "score_raw_cosine"}:
            s_prompt = max(-1.0, min(1.0, prompt_raw))
        elif prompt_metric == "margin":
            s_prompt = prompt_raw
        else:
            s_prompt = max(0.0, min(1.0, prompt_raw))
        pair = paired_scores.get(sid, {})
        pair_hit = float(pair.get("s_semantic_pair_hit", 0.0)) > 0.0
        s_anchor = max(0.0, min(1.0, float(pair.get("s_semantic_pair", 0.0)))) if pair_hit else 0.0

        if is_guided:
            guided_count += 1
            if pair_hit:
                anchor_hit_count += 1
            w_anchor = guided_w_anchor
            w_prompt = guided_w_prompt
            route = "guided"
        else:
            if str(row.get("source", "")) == "synthetic":
                prompt_only_count += 1
            w_anchor = 0.0
            w_prompt = 1.0
            route = "prompt_only"
        s_final = max(0.0, min(1.0, (w_anchor * s_anchor) + (w_prompt * s_prompt)))

        out[sid] = {
            "s_anchor": s_anchor,
            "s_prompt": s_prompt,
            "s_final": s_final,
            "w_anchor": w_anchor,
            "w_prompt": w_prompt,
            "phase1_route": route,
        }

    return out, {
        "enabled": True,
        "phase1_version": "v1_minimal",
        "prompt_metric": prompt_metric,
        "guided_w_anchor": guided_w_anchor,
        "guided_w_prompt": guided_w_prompt,
        "guided_synth_count": guided_count,
        "prompt_only_synth_count": prompt_only_count,
        "guided_anchor_hit_count": anchor_hit_count,
    }


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
    cache_path = Path(str(clip_cfg.get("embed_cache_path", filter_dir / "clip_embed_cache.json")))
    phase1_cfg = dict(filter_cfg.get("phase1_semantic", {}))
    prompt_field = str(phase1_cfg.get("prompt_field", "effective_prompt_text"))
    keep_real_always = bool(filter_cfg.get("keep_real_always", True))

    embeddings, runtime, cache_stats = build_image_embeddings(
        rows=rows,
        model_id=model_id,
        device_cfg=device,
        cache_path=cache_path,
    )

    sid_list = [str(r.get("sample_id", "")) for r in rows]
    prompt_scores: Dict[str, float]
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
    prompt_metric = str(phase1_cfg.get("prompt_metric", "score")).strip().lower()
    if prompt_metric in {"margin", "margin_norm"}:
        margin_scores = compute_prompt_margin_scores(
            rows=rows,
            image_embeddings=embeddings,
            runtime=runtime,
            pos_prompt=prompt_text,
            neg_prompts=[str(x) for x in clip_cfg.get("negative_prompts", [])],
            prompt_score_mode=prompt_score_mode,
        )
        key = "s_prompt_margin_norm" if prompt_metric == "margin_norm" else "s_prompt_margin"
        prompt_scores = {sid: float(v.get(key, 0.0)) for sid, v in margin_scores.items()}
    elif prompt_metric in {"raw_cosine", "score_raw_cosine"}:
        mapped = compute_prompt_scores(
            rows=rows,
            image_embeddings=embeddings,
            runtime=runtime,
            prompt_text=prompt_text,
            prompt_score_mode="cosine",
            prompt_field=prompt_field,
        )
        prompt_scores = {sid: (float(v) * 2.0) - 1.0 for sid, v in mapped.items()}
    else:
        prompt_scores = compute_prompt_scores(
            rows=rows,
            image_embeddings=embeddings,
            runtime=runtime,
            prompt_text=prompt_text,
            prompt_score_mode=prompt_score_mode,
            prompt_field=prompt_field,
        )

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
        semantic_scores={},
        paired_scores=paired_scores,
        prompt_scores=prompt_scores,
        phase1_cfg=phase1_cfg,
    )

    score_rows: List[Dict[str, Any]] = []
    for row in rows:
        sample_id = str(row.get("sample_id", "unknown"))
        source = str(row.get("source", ""))
        p = phase1_scores.get(sample_id, {})
        s_anchor = float(p.get("s_anchor", 0.0))
        s_prompt = float(p.get("s_prompt", 0.0))
        s_final = float(p.get("s_final", s_prompt))
        w_anchor = float(p.get("w_anchor", 0.0))
        w_prompt = float(p.get("w_prompt", 1.0))
        phase1_route = str(p.get("phase1_route", "prompt_only"))
        decision = choose_decision(s_final, accept_threshold, uncertain_low, uncertain_high)
        decision_basis = "phase1_v1_score"
        keep = decision == "accept"
        if keep_real_always and source == "real":
            decision = "accept"
            keep = True
            s_final = 1.0
            decision_basis = "keep_real_always"
        score_rows.append(
            {
                "image_id": sample_id,
                "sample_id": sample_id,
                "source": source,
                "phase1_route": phase1_route,
                "s_anchor": round(s_anchor, 6),
                "s_prompt": round(s_prompt, 6),
                "w_anchor": round(w_anchor, 6),
                "w_prompt": round(w_prompt, 6),
                "s_final": round(s_final, 6),
                "final_score": round(s_final, 6),
                "keep": keep,
                "score_asf": round(s_final, 6),
                "decision": decision,
                "decision_basis": decision_basis,
                "clip_model_id": model_id,
                "clip_device": runtime.device,
            }
        )

    report_extra: Dict[str, Any] = {
        "clip_model_id": model_id,
        "clip_device": runtime.device,
        "keep_real_always": keep_real_always,
        "strategy": "phase1_v1",
        "prompt_text_present": bool(prompt_text.strip()),
        "prompt_text_source": str(clip_cfg.get("prompt_text_source", "")),
        "prompt_score_mode": prompt_score_mode,
        "phase1_semantic": {
            **phase1_state,
            "paired": phase1_pair_state,
            "prompt_field": prompt_field,
        },
        **cache_stats,
    }
    real_prompt_values = sorted(
        float(prompt_scores.get(str(r.get("sample_id", "")), 0.0))
        for r in rows
        if str(r.get("source", "")) == "real"
    )
    if real_prompt_values:
        def _pick_q(vals: List[float], q: float) -> float:
            idx = int(round((len(vals) - 1) * q))
            idx = max(0, min(len(vals) - 1, idx))
            return float(vals[idx])
        report_extra["phase1_semantic"]["prompt_real_quantiles"] = {
            "count": len(real_prompt_values),
            "q05": round(_pick_q(real_prompt_values, 0.05), 6),
            "q10": round(_pick_q(real_prompt_values, 0.10), 6),
            "q50": round(_pick_q(real_prompt_values, 0.50), 6),
            "q90": round(_pick_q(real_prompt_values, 0.90), 6),
            "q95": round(_pick_q(real_prompt_values, 0.95), 6),
        }
    return score_rows, report_extra


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter phase1 (compose v1 only)")
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
    mode = str(filter_cfg.get("mode", "compose"))
    if mode != "compose":
        raise ValueError(
            f"unsupported filter.mode: {mode}. "
            "Only compose is supported in the simplified phase1 implementation."
        )

    filter_dir = run_dir / "filter"
    splits_dir = filter_dir / "splits"
    filter_dir.mkdir(parents=True, exist_ok=True)
    splits_dir.mkdir(parents=True, exist_ok=True)
    phase1_compare_log_path = filter_dir / "phase1_compare_log.jsonl"
    legacy_artifacts_removed: List[str] = []
    if mode == "compose" and phase1_compare_log_path.exists():
        phase1_compare_log_path.unlink()
        legacy_artifacts_removed.append(str(phase1_compare_log_path))

    score_rows, report_extra = run_composed_clip_filter(
        rows=rows,
        filter_dir=filter_dir,
        accept_threshold=accept_threshold,
        uncertain_low=uncertain_low,
        uncertain_high=uncertain_high,
        filter_cfg=filter_cfg,
    )

    ranking_state = _apply_topk_review_selection(score_rows=score_rows, filter_cfg=filter_cfg)
    if bool(ranking_state.get("enabled", False)):
        report_extra = dict(report_extra)
        report_extra["ranking_review"] = ranking_state

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
        "legacy_artifacts_removed": legacy_artifacts_removed,
        **report_extra,
    }
    write_json(filter_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
