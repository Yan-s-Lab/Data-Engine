# 1) Summary
- Implement `filter/filter_stages/filter1/main.py` as the formal post-threshold filtering stage.
- This stage consumes `input_manifests` rows, computes SigLIP2 margin scores using configured positive/negative prompts, and applies externally produced `best_threshold` for accept/reject decisions.

# 2) Scope
## In scope
- Add shared SigLIP2 inference core utility to avoid duplicated model inference logic.
- Implement filter1 stage entrypoint and decision/report outputs.
- Reuse existing top-k margin core (`common/siglip2_margin_threshold.py`).
- Add minimal tests for filter1 threshold/row contract logic.

## Out of scope
- Re-training or re-solving threshold in filter1 stage.
- Pipeline phase wiring changes in `filter/run_filter.py`.
- Non-prompt guided modes beyond passthrough/skip markers.

# 3) Layer Placement (Orchestration / Components / Core)
- Orchestration: `filter/filter_stages/filter1/main.py` (stage runner CLI).
- Core:
  - `common/siglip2_inference.py` shared SigLIP2 model loading + logits inference.
  - Existing `common/siglip2_margin_threshold.py` reused for margin aggregation.
- Placement keeps model-agnostic math in core and stage I/O in component runner.

# 4) Interfaces (Signatures)
## New/changed public interfaces
- `common.siglip2_inference.load_siglip2_runtime(model_id: str, device_cfg: str) -> tuple[Any, Any, str]`
- `common.siglip2_inference.compute_siglip2_logits_for_image(*, model: Any, processor: Any, image_path: Path, prompts: list[str], device: str) -> list[float]`
- `python filter/filter_stages/filter1/main.py --config <yaml> [--threshold <float>] [--threshold-report <json>] [--top-k 3] [--output-dir <dir>]`

## Backward compatibility
- Additive only; no existing caller interface is broken.

# 5) Data Contracts (Explicit Schemas)
## Step Inputs
- Manifest row (dict contract):
  - Required: `image_path` (or fallback `imagepath|path`)
  - Optional: `sample_id`, `generative_type`
- Threshold input:
  - CLI `--threshold` OR JSON file containing `best_threshold`.

## Step Outputs
- `filter1_scores.jsonl` rows:
  - `sample_id`, `image_path`, `generative_type`, `margin`, `pos_score`, `neg_score`, `threshold`, `decision`
- split files:
  - `splits/accept.jsonl`, `splits/reject.jsonl`
- report:
  - `report.json` summary counts and runtime config.

# 6) Config Contract
- Used keys:
  - `run.artifacts_root`, `run.run_id`
  - `filter.input_manifests` (list or string)
  - `filter.clip.model_id`, `filter.clip.device`
  - `filter.clip.compared_prompt.positive`, `filter.clip.compared_prompt.negative`
- Optional key:
  - `filter.siglip2_margin_threshold` fallback threshold source.
- CLI precedence:
  1. `--threshold`
  2. `--threshold-report` with `best_threshold`
  3. `filter.siglip2_margin_threshold`

# 7) Registry / Dispatch Plan (If applicable)
- Not applicable. This is a standalone stage entry script.

# 8) Dependency Direction Check
- Orchestration imports:
  - `filter/filter_stages/filter1/main.py` -> `common.*`
- Components imports:
  - none added.
- Core imports:
  - `common/siglip2_inference.py` uses stdlib + torch/transformers/PIL only.

# 9) Test Plan (Minimum)
- Unit tests:
  - threshold source precedence and validation
  - manifest row normalization contract
- Command:
  - `conda run -n dataengine python test/test_filter1_main.py`

# 10) Risks & Mitigations
- Risk: threshold missing from handoff.
  - Mitigation: strict validation with explicit error.
- Risk: manifest schema variance.
  - Mitigation: support common path aliases and stable normalization.
- Risk: runtime cost.
  - Mitigation: single forward per image with merged prompts.

# 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote
