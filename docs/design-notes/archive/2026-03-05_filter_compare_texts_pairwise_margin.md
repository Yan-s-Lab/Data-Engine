## 1) Summary
- Replace SigLIP compare-texts scoring in filter phase1 from sigmoid-based aggregation to pairwise logit-margin aggregation.
- Motivation: SigLIP logits/sigmoid are not calibrated probabilities; ranking/relative comparison is more stable and fair for positive-vs-negative text groups.

## 2) Scope
### In scope
- `filter/filter_stages/clip_prompt_score.py`: compare-texts scoring algorithm update.
- `filter/pipeline_engine/phase1_dual_signal.py`: prompt score mode resolution and report metadata alignment.
- `test/test_filter_phase1_semantic.py`: unit tests for new compare-texts behavior.
- Config compatibility for existing compare-texts keys in `filter.clip.*`.

### Out of scope
- Pipeline step ordering and orchestrator flow.
- Non-compare prompt scoring path (`compute_prompt_scores` cosine path).
- Anchor pair semantic scoring logic.

## 3) Layer Placement (Orchestration / Components / Core)
- Changed layers:
  - Components: `filter/pipeline_engine/phase1_dual_signal.py`
  - Core-like reusable stage logic: `filter/filter_stages/clip_prompt_score.py`
- Rationale: This is algorithmic scoring behavior inside filter component/stage. No orchestration wiring changes required.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `compute_compare_texts_prompt_scores(...) -> tuple[Dict[str, float], Dict[str, Any]]`
  - Signature unchanged.
  - Internal contract changes from sigmoid-based group score aggregation to pairwise margin aggregation over positive vs negative groups.
- `aggregate_compare_texts_group_scores(...) -> Dict[str, float]`
  - Signature updated to accept pre-reduced positive/negative margin statistics (internal helper-level API in same module).

Inputs:
- Existing row/image/runtime inputs unchanged.
- Existing compare-texts config keys still accepted.

Outputs:
- `out[sid]` remains `[0,1]` scalar `s_prompt` for downstream thresholds.
- Report metadata adds margin calculation mode fields.

Error handling:
- Missing images/text groups continue to return safe defaults (`0.0`) and state diagnostics.

### Backward compatibility
- No compatibility layer is preserved for legacy compare-texts grouping/weighting.
- New contract requires `compare-texts.positive` and `compare-texts.negative` only.
- Threshold retuning may still be needed.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Dict contract (existing): rows require `sample_id`, `image_path`; filter cfg requires `filter.clip.compare-texts` groups.

### Step Outputs
- `score_row` still provides `s_prompt` in `[0,1]`.
- Compare report includes:
  - `mode: pairwise_margin`
  - `pairwise_reduce`
  - `margin_norm` metadata

## 6) Config Contract
- Used keys:
  - `filter.clip.compare-texts`
  - `filter.clip.prompt_score_mode`
- Defaults:
  - SigLIP default prompt mode resolved to margin-based mode.
- Validation:
  - compare-texts must contain non-empty `positive` and `negative` lists.

Example snippet:
```yaml
filter:
  clip:
    model_id: google/siglip2-so400m-patch16-naflex
    compare-texts:
      positive: [...]
      negative: [...]
```

## 7) Registry / Dispatch Plan (If applicable)
- No new pipeline step or registry entry.
- Existing phase1 dispatch remains unchanged.

## 8) Dependency Direction Check
- Orchestration imports: unchanged.
- Components imports: unchanged; `phase1_dual_signal` imports filter stage functions.
- Core imports: `clip_prompt_score` does not import orchestration/component modules.

## 9) Test Plan (Minimum)
- Update unit tests in `test/test_filter_phase1_semantic.py`:
  - pairwise margin aggregation math and clamp behavior.
  - compare-texts path invocation unchanged and report metadata available.
- Run:
  - `python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v`

## 10) Risks & Mitigations
- Risk: Existing thresholds tuned for prior sigmoid aggregation may shift.
- Mitigation: Keep output in `[0,1]` via monotonic normalization and expose report metadata for diagnosis.
- Risk: Configs with only positive or only negative groups.
- Mitigation: Fallback to one-sided score path with explicit diagnostic reason.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [ ] Git commit message:
- [ ] Pushed to remote
