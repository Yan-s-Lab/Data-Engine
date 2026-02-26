from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List

from filter.filter_stages import (
    build_image_embeddings,
    compute_anchor_ood_scores,
    compute_anchor_semantic_scores,
    compute_consistency_scores,
    compute_duplicate_similarity,
    compute_multicrop_consistency_scores,
    compute_paired_anchor_semantic_scores,
    compute_prompt_margin_scores,
    compute_prompt_scores,
    compute_quality_scores,
    fit_anchor_ood_stats,
)


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


def _resolve_prompt_score_mode(clip_cfg: Dict[str, Any], model_id: str) -> str:
    explicit = str(clip_cfg.get("prompt_score_mode", "")).strip().lower()
    if explicit:
        return explicit
    if "siglip" in model_id.strip().lower():
        return "siglip_sigmoid"
    return "cosine"


def run_staged_clip_filter(
    rows: List[Dict[str, Any]],
    filter_dir: Path,
    accept_threshold: float,
    uncertain_low: float,
    uncertain_high: float,
    filter_cfg: Dict[str, Any],
    choose_decision_fn: Callable[[float, float, float, float], str],
    build_phase1_semantic_scores_fn: Callable[..., tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]],
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
    phase1_scores, phase1_state = build_phase1_semantic_scores_fn(
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
            decision = choose_decision_fn(final_score, accept_threshold, uncertain_low, uncertain_high)
            decision_basis = "weighted_stage_score"
            keep = decision == "accept"
            gate_fail = ""

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
