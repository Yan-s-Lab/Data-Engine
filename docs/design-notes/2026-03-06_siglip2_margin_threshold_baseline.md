# 1) Summary
- Add a standalone evaluator to score labeled images with SigLIP2 raw logits using positive/negative prompt groups and top-k aggregation.
- Compute per-image margin (`pos_topk_mean - neg_topk_mean`) and sweep thresholds over unique margins to select the best F1 threshold.

# 2) Scope
## In scope
- New orchestration script to run evaluation from config + labeled JSON.
- New core utility module for top-k aggregation, margin computation, threshold sweep, and metrics.
- Unit tests for core threshold logic and aggregation.
- Quickstart doc update for command usage.

## Out of scope
- No change to existing filter phase decision flow.
- No cross-validation, no hyperparameter tuning, no sigmoid calibration.
- No pipeline ordering changes.

# 3) Layer Placement (Orchestration / Components / Core)
- Orchestration change: `filter/evaluate_siglip2_margin_threshold.py`
  - Reads config and labeled file, runs model inference, writes report.
- Core change: `common/siglip2_margin_threshold.py`
  - Pure scoring/threshold functions independent of pipeline orchestration.
- This placement keeps model/run wiring in orchestration and math/metric logic in core.

# 4) Interfaces (Signatures)
## New/changed public interfaces
- `common.siglip2_margin_threshold.compute_margin(pos_logits: Sequence[float], neg_logits: Sequence[float], *, top_k: int = 3) -> dict[str, float]`
  - Inputs: positive/negative raw logits and top-k.
  - Outputs: `{"pos_score": float, "neg_score": float, "margin": float, "effective_k": int}`.
  - Error handling: raises `ValueError` when either logits group is empty.

- `common.siglip2_margin_threshold.sweep_best_f1_threshold(margins: Sequence[float], labels: Sequence[int]) -> dict[str, Any]`
  - Inputs: margins and binary labels (`1=accept`, `0=reject`).
  - Outputs: best threshold and metrics (`precision`, `recall`, `f1`, confusion matrix).
  - Error handling: raises `ValueError` on length mismatch or empty input.

- `common.siglip2_margin_threshold.sweep_best_threshold_at_min_precision(margins: Sequence[float], labels: Sequence[int], *, min_precision: float) -> dict[str, Any]`
  - Inputs: margins, labels, and minimum precision constraint.
  - Outputs: threshold that maximizes recall under `precision >= min_precision`.
  - Error handling: raises `ValueError` when no threshold satisfies the constraint.

- `python filter/evaluate_siglip2_margin_threshold.py --config <yaml> [--top-k 3] [--min-precision 0.9] [--output <json>]`
  - Reads:
    - `filter.siglip2_baseline_labeled`
    - `filter.clip.compared_prompt.positive`
    - `filter.clip.compared_prompt.negative`
  - Writes JSON report with per-image margins and best threshold metrics.

## Backward compatibility
- No existing interface is changed.
- New script is additive and optional.

# 5) Data Contracts (Explicit Schemas)
## Step Inputs
- Labeled JSON item contract:
  - Required fields: `imagepath: str`, `label: str` (`accept` or `reject`)

## Step Outputs
- Report JSON contract:
  - `best_threshold: float`
  - `precision: float`
  - `recall: float`
  - `f1: float`
  - `confusion_matrix: [[tn, fp], [fn, tp]]`
  - `top_k: int`
  - `model_id: str`
  - `total: int`
  - `samples: [{"imagepath": str, "label": str, "label_binary": int, "margin": float, "pos_score": float, "neg_score": float}]`

# 6) Config Contract
- Config keys used:
  - `filter.siglip2_baseline_labeled: str`
  - `filter.clip.model_id: str` (default: `google/siglip2-so400m-patch16-naflex`)
  - `filter.clip.device: str` (`auto|cpu|cuda`)
  - `filter.clip.compared_prompt.positive: list[str]`
  - `filter.clip.compared_prompt.negative: list[str]`
- Defaults:
  - `top_k=3` (CLI default)
  - `min_precision=None` (default objective is max F1)
  - device resolves to `cuda` when available if config is `auto`
- Validation rules:
  - prompt groups must both be non-empty
  - labels must be in `{accept, reject}`

Example snippet:
```yaml
filter:
  siglip2_baseline_labeled: artifacts/tmp/siglip2_baseline_labeled.json
  clip:
    model_id: google/siglip2-so400m-patch16-naflex
    device: auto
    compared_prompt:
      positive: ["a photo contains person"]
      negative: ["a photo with no person"]
```

# 7) Registry / Dispatch Plan (If applicable)
- Not applicable. No new pipeline phase registration.

# 8) Dependency Direction Check
Confirm imports follow: Orchestration -> Components -> Core
- Orchestration imports:
  - `filter/evaluate_siglip2_margin_threshold.py` imports `common.*` modules and external libs.
- Components imports:
  - none added.
- Core imports:
  - `common/siglip2_margin_threshold.py` uses Python stdlib only.

# 9) Test Plan (Minimum)
- Unit tests:
  - `test/test_siglip2_margin_threshold.py` for top-k margin aggregation and threshold sweep.
- Integration test:
  - Not required (no pipeline ordering/registry change).
- Run command:
  - `pytest -q test/test_siglip2_margin_threshold.py`

# 10) Risks & Mitigations
- Risk: large prompt list x image count may be slow.
  - Mitigation: single forward per image with merged prompt list.
- Risk: path resolution ambiguity for `imagepath`.
  - Mitigation: resolve relative paths against labeled JSON directory first, then workspace.
- Risk: ties in best F1 across thresholds.
  - Mitigation: deterministic tie-break rule documented in code.

# 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote
