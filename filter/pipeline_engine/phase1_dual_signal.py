from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from common.filter_prompt_contract import resolve_prompt_groups
from filter.filter_stages import (
    build_image_embeddings,
    compute_compare_texts_prompt_scores,
    compute_paired_anchor_semantic_scores,
    compute_prompt_scores,
)
from .io_ops import is_real_guided_synth


PHASE_ID = "phase1_dual_signal"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _resolve_prompt_score_mode(model_id: str, clip_cfg: Dict[str, Any]) -> str:
    if "siglip" in model_id.strip().lower():
        return "siglip_pairwise_margin"
    return str(clip_cfg.get("prompt_score_mode", "cosine"))


def _phase1_runtime_config(filter_cfg: Dict[str, Any], filter_dir: Path) -> Dict[str, Any]:
    clip_cfg = dict(filter_cfg.get("clip", {}))
    phase1_cfg = dict(filter_cfg.get("phase1_semantic", {}))
    model_id = str(clip_cfg.get("model_id", "openai/clip-vit-base-patch32"))
    compare_cfg = _resolve_compare_texts_config(clip_cfg)
    return {
        "clip_cfg": clip_cfg,
        "phase1_cfg": phase1_cfg,
        "model_id": model_id,
        "device": str(clip_cfg.get("device", "auto")),
        "prompt_text": str(clip_cfg.get("prompt_text", filter_cfg.get("prompt_text", ""))),
        "prompt_field": str(phase1_cfg.get("prompt_field", "effective_prompt_text")),
        "keep_real_always": bool(filter_cfg.get("keep_real_always", True)),
        "prompt_score_mode": _resolve_prompt_score_mode(model_id, clip_cfg),
        "cache_path": Path(str(clip_cfg.get("embed_cache_path", filter_dir / "clip_embed_cache.json"))),
        "compare_texts_cfg": compare_cfg,
    }


def _resolve_compare_texts_config(clip_cfg: Dict[str, Any]) -> Dict[str, Any]:
    groups, groups_source = resolve_prompt_groups(clip_cfg)
    positive = groups.get("positive", [])
    negative = groups.get("negative", [])
    if not positive or not negative:
        return {"enabled": False, "groups": {}, "groups_source": ""}
    return {
        "enabled": True,
        "groups": {"positive": positive, "negative": negative},
        "groups_source": groups_source,
    }


def _build_score_row(
    *,
    row: Dict[str, Any],
    phase1_cfg: Dict[str, Any],
    prompt_scores: Dict[str, float],
    paired_scores: Dict[str, Dict[str, Any]],
    keep_real_always: bool,
    model_id: str,
    clip_device: str,
    compare_details: Dict[str, Any],
) -> Tuple[Dict[str, Any], str, bool]:
    sid = str(row.get("sample_id", ""))
    source = str(row.get("source", ""))
    route = "guided" if is_real_guided_synth(row=row, phase1_cfg=phase1_cfg) else "prompt_only"
    s_prompt = _clamp01(prompt_scores.get(sid, 0.0))
    pair = paired_scores.get(sid, {})
    s_anchor_hit = 1.0 if float(pair.get("s_semantic_pair_hit", 0.0)) > 0.0 else 0.0
    s_anchor = _clamp01(pair.get("s_semantic_pair", 0.0)) if s_anchor_hit > 0.0 else 0.0
    s_final = min(s_prompt, s_anchor) if route == "guided" and s_anchor_hit > 0.0 else s_prompt

    decision = "uncertain"
    decision_basis = "phase1_dual_signal_pending"
    keep = False
    if keep_real_always and source == "real":
        decision = "accept"
        decision_basis = "keep_real_always"
        keep = True
        s_final = 1.0

    score_row = {
        "image_id": sid,
        "sample_id": sid,
        "source": source,
        "phase1_route": route,
        "s_anchor": round(s_anchor, 6),
        "s_anchor_hit": round(s_anchor_hit, 6),
        "s_prompt": round(s_prompt, 6),
        "s_final": round(s_final, 6),
        "final_score": round(s_final, 6),
        "keep": keep,
        "score_asf": round(s_final, 6),
        "decision": decision,
        "decision_basis": decision_basis,
        "clip_model_id": model_id,
        "clip_device": clip_device,
        "prompt_compare_log": compare_details,
    }
    return score_row, route, s_anchor_hit > 0.0


def _build_phase1_report(
    *,
    runtime_cfg: Dict[str, Any],
    runtime_device: str,
    cache_stats: Dict[str, Any],
    paired_state: Dict[str, Any],
    guided_count: int,
    prompt_only_count: int,
    guided_anchor_hit_count: int,
    compare_texts_state: Dict[str, Any],
) -> Dict[str, Any]:
    clip_cfg = runtime_cfg["clip_cfg"]
    return {
        "clip_model_id": runtime_cfg["model_id"],
        "clip_device": runtime_device,
        "keep_real_always": runtime_cfg["keep_real_always"],
        "strategy": "phase1_dual_signal",
        "prompt_text_present": bool(runtime_cfg["prompt_text"].strip()),
        "prompt_text_source": str(clip_cfg.get("prompt_text_source", "")),
        "prompt_score_mode": runtime_cfg["prompt_score_mode"],
        "compare_texts": compare_texts_state,
        "compare_texts_groups_source": str(runtime_cfg.get("compare_texts_cfg", {}).get("groups_source", "")),
        "phase1_semantic": {
            "enabled": True,
            "phase1_version": "dual_signal",
            "guided_synth_count": guided_count,
            "prompt_only_synth_count": prompt_only_count,
            "guided_anchor_hit_count": guided_anchor_hit_count,
            "paired": paired_state,
            "prompt_field": runtime_cfg["prompt_field"],
        },
        **cache_stats,
    }


def compute_phase1_score_rows(
    rows: List[Dict[str, Any]],
    *,
    filter_dir: Path,
    filter_cfg: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    runtime_cfg = _phase1_runtime_config(filter_cfg, filter_dir)
    phase1_cfg = runtime_cfg["phase1_cfg"]

    embeddings, runtime, cache_stats = build_image_embeddings(
        rows=rows,
        model_id=runtime_cfg["model_id"],
        device_cfg=runtime_cfg["device"],
        cache_path=runtime_cfg["cache_path"],
    )

    compare_cfg = dict(runtime_cfg.get("compare_texts_cfg", {}))
    compare_state: Dict[str, Any] = {"enabled": False, "reason": "compare_texts_disabled"}
    compare_details_by_sid: Dict[str, Dict[str, Any]] = {}
    if bool(compare_cfg.get("enabled", False)):
        prompt_scores, compare_state = compute_compare_texts_prompt_scores(
            rows=rows,
            runtime=runtime,
            compare_texts=dict(compare_cfg.get("groups", {})),
        )
        compare_details_by_sid = dict(compare_state.pop("sample_details", {}))
    else:
        prompt_scores = compute_prompt_scores(
            rows=rows,
            image_embeddings=embeddings,
            runtime=runtime,
            prompt_text=runtime_cfg["prompt_text"],
            prompt_score_mode=runtime_cfg["prompt_score_mode"],
            prompt_field=runtime_cfg["prompt_field"],
        )
    paired_scores, paired_state = compute_paired_anchor_semantic_scores(
        rows=rows,
        image_embeddings=embeddings,
        cfg=phase1_cfg,
    )

    score_rows: List[Dict[str, Any]] = []
    guided_count = 0
    prompt_only_count = 0
    guided_anchor_hit_count = 0

    for row in rows:
        score_row, route, anchor_hit = _build_score_row(
            row=row,
            phase1_cfg=phase1_cfg,
            prompt_scores=prompt_scores,
            paired_scores=paired_scores,
            keep_real_always=runtime_cfg["keep_real_always"],
            model_id=runtime_cfg["model_id"],
            clip_device=runtime.device,
            compare_details=dict(compare_details_by_sid.get(str(row.get("sample_id", "")), {})),
        )
        source = str(score_row.get("source", ""))
        if route == "guided":
            guided_count += 1
        elif source == "synthetic":
            prompt_only_count += 1
        if route == "guided" and anchor_hit:
            guided_anchor_hit_count += 1
        score_rows.append(score_row)

    report_extra = _build_phase1_report(
        runtime_cfg=runtime_cfg,
        runtime_device=runtime.device,
        cache_stats=cache_stats,
        paired_state=paired_state,
        guided_count=guided_count,
        prompt_only_count=prompt_only_count,
        guided_anchor_hit_count=guided_anchor_hit_count,
        compare_texts_state=compare_state,
    )
    return score_rows, report_extra


def _parse_selection_cfg(phase_cfg: Dict[str, Any]) -> Dict[str, Any]:
    prompt_accept_threshold = float(phase_cfg.get("prompt_accept_threshold", 0.5))
    pair_accept_threshold = float(phase_cfg.get("pair_accept_threshold", 0.5))
    missing_pair_policy = str(phase_cfg.get("missing_pair_policy", "uncertain")).strip().lower()
    if missing_pair_policy not in {"uncertain", "reject"}:
        missing_pair_policy = "uncertain"
    return {
        "target_source": str(phase_cfg.get("target_source", "synthetic")).strip(),
        "hard_reject": bool(phase_cfg.get("hard_reject", False)),
        "prompt_accept_threshold": prompt_accept_threshold,
        "prompt_uncertain_threshold": float(phase_cfg.get("prompt_uncertain_threshold", prompt_accept_threshold)),
        "pair_accept_threshold": pair_accept_threshold,
        "pair_uncertain_threshold": float(phase_cfg.get("pair_uncertain_threshold", pair_accept_threshold)),
        "missing_pair_policy": missing_pair_policy,
    }


def _count_decision(row: Dict[str, Any], counters: Dict[str, int]) -> None:
    decision = str(row.get("decision", ""))
    if decision == "accept":
        counters["accept_count"] += 1
    elif decision == "uncertain":
        counters["uncertain_count"] += 1
    else:
        counters["reject_count"] += 1


def _apply_guided_decision(row: Dict[str, Any], cfg: Dict[str, Any], counters: Dict[str, int]) -> None:
    counters["guided_total"] += 1
    s_prompt = float(row.get("s_prompt", 0.0))
    s_anchor = float(row.get("s_anchor", 0.0))
    s_anchor_hit = float(row.get("s_anchor_hit", 0.0)) > 0.0
    if not s_anchor_hit:
        if cfg["missing_pair_policy"] == "reject" and cfg["hard_reject"]:
            row["decision"] = "reject"
            row["decision_basis"] = "phase1_dual_signal_guided_pair_missing_reject"
        else:
            row["decision"] = "uncertain"
            row["decision_basis"] = "phase1_dual_signal_guided_pair_missing_uncertain"
        row["keep"] = row["decision"] == "accept"
        _count_decision(row, counters)
        return

    pass_prompt_accept = s_prompt >= cfg["prompt_accept_threshold"]
    pass_pair_accept = s_anchor >= cfg["pair_accept_threshold"]
    pass_prompt_uncertain = s_prompt >= cfg["prompt_uncertain_threshold"]
    pass_pair_uncertain = s_anchor >= cfg["pair_uncertain_threshold"]
    if pass_prompt_accept and pass_pair_accept:
        row["decision"] = "accept"
        row["decision_basis"] = "phase1_dual_signal_guided_accept"
    elif cfg["hard_reject"] and (not pass_prompt_uncertain or not pass_pair_uncertain):
        row["decision"] = "reject"
        row["decision_basis"] = "phase1_dual_signal_guided_reject"
    else:
        row["decision"] = "uncertain"
        row["decision_basis"] = "phase1_dual_signal_guided_uncertain"
    row["keep"] = row["decision"] == "accept"
    _count_decision(row, counters)


def _apply_prompt_only_decision(row: Dict[str, Any], cfg: Dict[str, Any], counters: Dict[str, int]) -> None:
    counters["prompt_only_total"] += 1
    s_prompt = float(row.get("s_prompt", 0.0))
    if s_prompt >= cfg["prompt_accept_threshold"]:
        row["decision"] = "accept"
        row["decision_basis"] = "phase1_dual_signal_prompt_accept"
    elif cfg["hard_reject"] and s_prompt < cfg["prompt_uncertain_threshold"]:
        row["decision"] = "reject"
        row["decision_basis"] = "phase1_dual_signal_prompt_reject"
    else:
        row["decision"] = "uncertain"
        row["decision_basis"] = "phase1_dual_signal_prompt_uncertain"
    row["keep"] = row["decision"] == "accept"
    _count_decision(row, counters)


def apply_dual_signal_selection(score_rows: List[Dict[str, Any]], phase_cfg: Dict[str, Any]) -> Dict[str, Any]:
    if not bool(phase_cfg.get("enabled", False)):
        return {"enabled": False}

    cfg = _parse_selection_cfg(phase_cfg)
    counters = {
        "accept_count": 0,
        "uncertain_count": 0,
        "reject_count": 0,
        "guided_total": 0,
        "prompt_only_total": 0,
    }

    for row in score_rows:
        src = str(row.get("source", ""))
        if src != cfg["target_source"]:
            _count_decision(row, counters)
            continue

        route = str(row.get("phase1_route", "prompt_only")).strip()
        if route == "guided":
            _apply_guided_decision(row, cfg, counters)
            continue
        _apply_prompt_only_decision(row, cfg, counters)

    return {
        "enabled": True,
        "target_source": cfg["target_source"],
        "hard_reject": cfg["hard_reject"],
        "prompt_accept_threshold": cfg["prompt_accept_threshold"],
        "prompt_uncertain_threshold": cfg["prompt_uncertain_threshold"],
        "pair_accept_threshold": cfg["pair_accept_threshold"],
        "pair_uncertain_threshold": cfg["pair_uncertain_threshold"],
        "missing_pair_policy": cfg["missing_pair_policy"],
        "guided_total": counters["guided_total"],
        "prompt_only_total": counters["prompt_only_total"],
        "accept_after_selection": counters["accept_count"],
        "uncertain_after_selection": counters["uncertain_count"],
        "reject_after_selection": counters["reject_count"],
    }


def run_phase(
    rows: List[Dict[str, Any]],
    *,
    filter_dir: Path,
    filter_cfg: Dict[str, Any],
    phase_cfg: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    score_rows, report_extra = compute_phase1_score_rows(rows=rows, filter_dir=filter_dir, filter_cfg=filter_cfg)
    dual_state = apply_dual_signal_selection(score_rows=score_rows, phase_cfg=phase_cfg)
    report_extra = dict(report_extra)
    report_extra["phase1_dual_signal"] = dual_state
    return score_rows, report_extra
