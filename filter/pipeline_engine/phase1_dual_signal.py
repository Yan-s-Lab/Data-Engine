from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from filter.filter_stages import build_image_embeddings, compute_paired_anchor_semantic_scores, compute_prompt_scores
from .io_ops import is_real_guided_synth


PHASE_ID = "phase1_dual_signal"


def compute_phase1_score_rows(
    rows: List[Dict[str, Any]],
    *,
    filter_dir: Path,
    filter_cfg: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    clip_cfg = dict(filter_cfg.get("clip", {}))
    phase1_cfg = dict(filter_cfg.get("phase1_semantic", {}))
    model_id = str(clip_cfg.get("model_id", "openai/clip-vit-base-patch32"))
    device = str(clip_cfg.get("device", "auto"))
    prompt_text = str(clip_cfg.get("prompt_text", filter_cfg.get("prompt_text", "")))
    prompt_field = str(phase1_cfg.get("prompt_field", "effective_prompt_text"))
    keep_real_always = bool(filter_cfg.get("keep_real_always", True))
    prompt_score_mode = "siglip_sigmoid" if "siglip" in model_id.strip().lower() else str(
        clip_cfg.get("prompt_score_mode", "cosine")
    )

    embeddings, runtime, cache_stats = build_image_embeddings(
        rows=rows,
        model_id=model_id,
        device_cfg=device,
        cache_path=Path(str(clip_cfg.get("embed_cache_path", filter_dir / "clip_embed_cache.json"))),
    )

    prompt_scores = compute_prompt_scores(
        rows=rows,
        image_embeddings=embeddings,
        runtime=runtime,
        prompt_text=prompt_text,
        prompt_score_mode=prompt_score_mode,
        prompt_field=prompt_field,
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
        sid = str(row.get("sample_id", ""))
        source = str(row.get("source", ""))
        route = "guided" if is_real_guided_synth(row=row, phase1_cfg=phase1_cfg) else "prompt_only"
        if route == "guided":
            guided_count += 1
        elif source == "synthetic":
            prompt_only_count += 1

        s_prompt = max(0.0, min(1.0, float(prompt_scores.get(sid, 0.0))))
        pair = paired_scores.get(sid, {})
        s_anchor_hit = 1.0 if float(pair.get("s_semantic_pair_hit", 0.0)) > 0.0 else 0.0
        s_anchor = max(0.0, min(1.0, float(pair.get("s_semantic_pair", 0.0)))) if s_anchor_hit > 0.0 else 0.0
        if route == "guided" and s_anchor_hit > 0.0:
            guided_anchor_hit_count += 1

        if route == "guided":
            s_final = min(s_prompt, s_anchor) if s_anchor_hit > 0.0 else 0.0
        else:
            s_final = s_prompt

        decision = "uncertain"
        decision_basis = "phase1_dual_signal_pending"
        keep = False
        if keep_real_always and source == "real":
            decision = "accept"
            decision_basis = "keep_real_always"
            keep = True
            s_final = 1.0

        score_rows.append(
            {
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
                "clip_device": runtime.device,
            }
        )

    report_extra: Dict[str, Any] = {
        "clip_model_id": model_id,
        "clip_device": runtime.device,
        "keep_real_always": keep_real_always,
        "strategy": "phase1_dual_signal",
        "prompt_text_present": bool(prompt_text.strip()),
        "prompt_text_source": str(clip_cfg.get("prompt_text_source", "")),
        "prompt_score_mode": prompt_score_mode,
        "phase1_semantic": {
            "enabled": True,
            "phase1_version": "dual_signal",
            "guided_synth_count": guided_count,
            "prompt_only_synth_count": prompt_only_count,
            "guided_anchor_hit_count": guided_anchor_hit_count,
            "paired": paired_state,
            "prompt_field": prompt_field,
        },
        **cache_stats,
    }
    return score_rows, report_extra


def apply_dual_signal_selection(score_rows: List[Dict[str, Any]], phase_cfg: Dict[str, Any]) -> Dict[str, Any]:
    if not bool(phase_cfg.get("enabled", False)):
        return {"enabled": False}

    target_source = str(phase_cfg.get("target_source", "synthetic")).strip()
    hard_reject = bool(phase_cfg.get("hard_reject", False))
    prompt_accept_threshold = float(phase_cfg.get("prompt_accept_threshold", 0.5))
    prompt_uncertain_threshold = float(phase_cfg.get("prompt_uncertain_threshold", prompt_accept_threshold))
    pair_accept_threshold = float(phase_cfg.get("pair_accept_threshold", 0.5))
    pair_uncertain_threshold = float(phase_cfg.get("pair_uncertain_threshold", pair_accept_threshold))
    missing_pair_policy = str(phase_cfg.get("missing_pair_policy", "uncertain")).strip().lower()
    if missing_pair_policy not in {"uncertain", "reject"}:
        missing_pair_policy = "uncertain"

    accept_count = 0
    uncertain_count = 0
    reject_count = 0
    guided_total = 0
    prompt_only_total = 0

    for row in score_rows:
        src = str(row.get("source", ""))
        if src != target_source:
            if str(row.get("decision", "")) == "accept":
                accept_count += 1
            elif str(row.get("decision", "")) == "uncertain":
                uncertain_count += 1
            else:
                reject_count += 1
            continue

        route = str(row.get("phase1_route", "prompt_only")).strip()
        s_prompt = float(row.get("s_prompt", 0.0))
        s_anchor = float(row.get("s_anchor", 0.0))
        s_anchor_hit = float(row.get("s_anchor_hit", 0.0)) > 0.0

        if route == "guided":
            guided_total += 1
            if not s_anchor_hit:
                if missing_pair_policy == "reject" and hard_reject:
                    row["decision"] = "reject"
                    row["decision_basis"] = "phase1_dual_signal_guided_pair_missing_reject"
                    reject_count += 1
                else:
                    row["decision"] = "uncertain"
                    row["decision_basis"] = "phase1_dual_signal_guided_pair_missing_uncertain"
                    uncertain_count += 1
                row["keep"] = row["decision"] == "accept"
                continue

            pass_prompt_accept = s_prompt >= prompt_accept_threshold
            pass_pair_accept = s_anchor >= pair_accept_threshold
            pass_prompt_uncertain = s_prompt >= prompt_uncertain_threshold
            pass_pair_uncertain = s_anchor >= pair_uncertain_threshold

            if pass_prompt_accept and pass_pair_accept:
                row["decision"] = "accept"
                row["decision_basis"] = "phase1_dual_signal_guided_accept"
                accept_count += 1
            elif hard_reject and (not pass_prompt_uncertain or not pass_pair_uncertain):
                row["decision"] = "reject"
                row["decision_basis"] = "phase1_dual_signal_guided_reject"
                reject_count += 1
            else:
                row["decision"] = "uncertain"
                row["decision_basis"] = "phase1_dual_signal_guided_uncertain"
                uncertain_count += 1
            row["keep"] = row["decision"] == "accept"
            continue

        prompt_only_total += 1
        if s_prompt >= prompt_accept_threshold:
            row["decision"] = "accept"
            row["decision_basis"] = "phase1_dual_signal_prompt_accept"
            accept_count += 1
        elif hard_reject and s_prompt < prompt_uncertain_threshold:
            row["decision"] = "reject"
            row["decision_basis"] = "phase1_dual_signal_prompt_reject"
            reject_count += 1
        else:
            row["decision"] = "uncertain"
            row["decision_basis"] = "phase1_dual_signal_prompt_uncertain"
            uncertain_count += 1
        row["keep"] = row["decision"] == "accept"

    return {
        "enabled": True,
        "target_source": target_source,
        "hard_reject": hard_reject,
        "prompt_accept_threshold": prompt_accept_threshold,
        "prompt_uncertain_threshold": prompt_uncertain_threshold,
        "pair_accept_threshold": pair_accept_threshold,
        "pair_uncertain_threshold": pair_uncertain_threshold,
        "missing_pair_policy": missing_pair_policy,
        "guided_total": guided_total,
        "prompt_only_total": prompt_only_total,
        "accept_after_selection": accept_count,
        "uncertain_after_selection": uncertain_count,
        "reject_after_selection": reject_count,
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
