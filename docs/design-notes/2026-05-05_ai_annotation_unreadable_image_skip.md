## 1) Summary
- Make AI pose annotation skip unreadable/corrupt generated images instead of aborting the whole experiment.
- Needed because the raw synthetic pool can contain corrupt ComfyUI PNG outputs, and one bad image should not stop fair ablation materialization.

## 2) Scope
### In scope
- Catch per-image prediction/read failures inside `label/run_ai_annotation.py`.
- Count failed images as `skipped` and record a compact error entry in the annotation report.
- Add a unit test for report helper behavior.

### Out of scope
- Repairing corrupt images.
- Changing generation, filtering, or training behavior.

## 3) Layer Placement (Orchestration / Components / Core)
- Orchestration:
  - `label/run_ai_annotation.py` is the stage entrypoint that owns annotation I/O and report writing.
- No core/component changes are needed.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `record_prediction_error(errors: list[dict], sample_id: str, image_path: Path, exc: Exception) -> None`
  - Inputs: mutable error list, sample id, image path, exception.
  - Outputs: appends one compact error dict.
  - Error handling: truncates exception message only; does not raise.

### Backward compatibility
- Existing CLI and config keys remain unchanged.
- Existing reports keep the same fields, with an added optional `prediction_errors` list.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Existing annotation manifest rows with image path fields.

### Step Outputs
- Existing:
  - `ai_annotations_manifest.jsonl`
  - `ai_annotation_report.json`
  - `ai_dataset/`
- Added report field:
  - `prediction_errors`: list of `{sample_id, image_path, error_type, error}`

## 6) Config Contract
- No config keys added.

## 7) Registry / Dispatch Plan
- Not applicable.

## 8) Dependency Direction Check
Confirm imports follow:
Orchestration -> Components -> Core

- Orchestration imports:
  - unchanged
- Components imports:
  - none
- Core imports:
  - unchanged

## 9) Test Plan (Minimum)
- Unit tests:
  - verify prediction errors are recorded compactly.
- Integration:
  - rerun raw synthetic annotation through the fair experiment plan.
- How to run tests:
  - `conda run -n dataengine python -m unittest discover -s test -p 'test_run_ai_annotation.py'`

## 10) Risks & Mitigations
- Risk: hiding systematic annotation failures.
- Mitigation: report includes error count/details through `prediction_errors`; high skipped count remains visible.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [x] Git commit message: `fix(annotation): skip unreadable synthetic images`
- [ ] Pushed to remote
