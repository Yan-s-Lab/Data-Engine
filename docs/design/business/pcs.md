# Business Design: PCS

## 1. Scope

PCS (Perturbation CLIP Similarity) evaluates sample quality/stability under controlled perturbations.

## 2. Responsibilities

- define perturbation set and embedding comparison logic
- support semantic alignment margin scoring (`pos - max(neg)`)
- support anchor-calibrated semantic consistency scoring
  - `s_semantic_anchor(x) = median_{r in X_real} Sim(E(x), E(r))`
- support multi-crop embedding consistency scoring for structure-split detection
- support anchor-manifold OOD distance for real-distribution guardrail
- produce accept/reject/uncertain decisions with scores
- expose policy parameters for feedback-driven updates
- support staged execution:
  - `clip_embed_cache.py`
  - `clip_prompt_score.py`
  - `clip_semantic_anchor.py`
  - `clip_consistency.py`
  - `clip_anchor_ood.py`
  - `clip_dedup.py`
  - `quality_rules.py`
- support composable execution (`filter.mode: compose`) where stage enablement and
  policy are configured separately:
  - `filter.stages[]`: stage switches by id (`semantic_anchor`, `prompt_score`, `prompt_margin`,
    `consistency`, `multicrop`, `anchor_ood`, `dedup`, `quality`)
  - `filter.policy`: decision policy (`weighted`, `tri_gate`,
    `tri_gate_plus_weighted`) with gate operators and threshold calibration source

## 3. Contracts

Inputs:
- normalized manifest rows with `sample_id`, `source`, `image_path`
- filter policy config:
  - perturbation setup (`grid_rows`, `grid_cols`, `swap_ratio`, `repeats`)
  - CLIP/SigLIP model/runtime setup (`clip_model_id` or `clip.model_id`, `device`)
  - prompt semantic score mode (`clip.prompt_score_mode`: `cosine` or `siglip_sigmoid`)
  - decision thresholds (`accept_threshold`, `uncertain_low`, `uncertain_high`)
  - tri-gate thresholds (`clip_margin_threshold`, `multicrop_threshold`, `ood_threshold_md2`) or quantile calibration rules
  - compose gates:
    - `metric` + `op` + (`threshold` or `threshold_from`)
    - `threshold_from` currently supports quantile tokens such as `q05_real`, `q99_real`
  - routed phase1 semantic policy (`filter.phase1_semantic`):
    - guided synthetic: `semantic_pair` (paired image-image)
    - prompt-only synthetic: `prompt_score` (SigLIP2 text-image)
    - fallback: `semantic_anchor`

Outputs:
- `filter/filter_scores.jsonl` rows containing:
  - `s_semantic_anchor` (anchor-calibrated semantic score, normalized to [0,1])
  - `s_semantic_anchor_raw` (raw median cosine similarity to anchor set)
  - `s_semantic_pair` (paired anchor similarity score for real-guided synthetic rows)
  - `s_phase1_semantic` (routed phase1 semantic score)
  - `score_pcs` (mean CLIP cosine similarity between original and perturbed images)
  - `s_prompt_margin` (semantic positive-negative margin)
  - `s_multicrop_consistency` (cross-crop pairwise consistency mean)
  - `ood_md2` (anchor Mahalanobis distance squared)
  - perturbation evidence (`pcs_similarity_min/max/mean`, `pcs_repeats`)
  - policy decision (`accept|reject|uncertain`)
- split manifests under `filter/splits/`

## 4. Invariants

- decisions are versioned by policy and perturbation setup
- PCS currently runs in `filter/run_filter.py` as a bridge-ready implementation
- in compose mode, stage metric computation and policy decision are explicit in config

## 5. Open Questions

- perturbation family selection by failure slice
- score calibration against real validation performance
