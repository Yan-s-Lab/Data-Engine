## 1) Summary
- Stabilize `filter/test.py` inference by making quantization policy explicit.
- Default to non-quantized execution for SigLIP2 local diagnostic runs to avoid `Half` vs `Byte` dtype mismatch and fallback-induced uncertainty.

## 2) Scope
### In scope
- Update `filter/test.py` quantization selection and fallback flow.
- Add minimal unit tests for quantization decision logic.
- Keep existing image loading and scoring behavior.

### Out of scope
- Any pipeline/orchestrator/filter-stage behavior changes.
- Any algorithmic change to SigLIP2 score computation (`logits_per_image -> sigmoid`).

## 3) Layer Placement (Orchestration / Components / Core)
- Changed layer: component-support script in `filter/` (`filter/test.py`) and its unit test.
- Why: issue is local diagnostic runtime behavior, not pipeline orchestration or core filtering logic.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `resolve_quantization_mode(requested_mode: str, ckpt: str, has_cuda: bool) -> str`
  - Inputs: user-requested mode (`auto|off|on`), model id, CUDA availability.
  - Output: effective mode (`off` or `on`) used for model loading.
  - Error handling: no exception; falls back to safe mode in `auto`.
- `main()`
  - Add CLI arg: `--quantization {auto,off,on}`.

### Backward compatibility
- Existing `python filter/test.py` continues to work.
- Default remains automatic but now resolves to stable non-quantized mode for SigLIP2.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Script runtime inputs:
  - `image_source: str`
  - `candidate_labels: list[str]`
  - `quantization: str` (`auto|off|on`)

### Step Outputs
- Script terminal output: label scores and first-label percentage.
- Runtime warning/info logs about quantization mode.

## 6) Config Contract
- No pipeline config keys added/changed.
- No registry/config wiring changes.

## 7) Registry / Dispatch Plan (If applicable)
- Not applicable.

## 8) Dependency Direction Check
Confirm imports follow:
Orchestration → Components → Core

- Orchestration imports: none changed.
- Components imports: `filter/test.py` imports external libs only.
- Core imports: none.

## 9) Test Plan (Minimum)
- Unit tests to add/modify:
  - Add tests for `resolve_quantization_mode` behavior in `test/test_filter_test_local_image_loading.py`.
- Integration test to add/modify:
  - None required (no pipeline path change).
- How to run tests:
  - `python -m unittest discover -s test -p 'test_filter_test_local_image_loading.py' -v`

## 10) Risks & Mitigations
- Risk: users expecting forced 4-bit by default may observe changed runtime mode.
- Mitigation: provide explicit `--quantization on` for opt-in and clear mode logging.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [x] Git commit message: `fix(filter-test): default siglip2 auto mode to non-quantized`
- [x] Pushed to remote
