## 1) Summary
- Remove project-specific experiment orchestration, result aggregation, and final-analysis documentation from the public repository surface.
- Needed because the public Data Engine repo should expose reusable pipeline capabilities, not private run scripts, final-analysis recipes, or figure/result aggregation workflow.

## 2) Scope
### In scope
- Delete private final-analysis scripts and configs.
- Remove the private aggregation stage from the YAML pipeline registry.
- Rewrite public-facing README/ROADMAP/docs references away from project-specific experiment instructions.
- Update tests that asserted private aggregation stage availability.

### Out of scope
- Rewriting git history.
- Removing generic Data Engine capabilities for dataloading, generation, filtering, labeling, training, or evaluation.
- Changing model behavior, dataset schemas, or pipeline execution semantics.

## 3) Layer Placement (Orchestration / Components / Core)
- Orchestration: `pipelines/run_yaml_pipeline.py` loses the private aggregation stage mapping and output check.
- Docs/configs: public-facing docs and example configs are narrowed to engine usage.
- Components/Core: no functional algorithm changes.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- Removed private result-aggregation stage name.
- Existing signatures remain unchanged:
  - `stage_output_ok(stage: str, run_dir: Path, config: Dict[str, Any] | None = None) -> bool`
  - pipeline scripts still accept `--config`.

### Backward compatibility
- Breaks private configs that reference the removed result-aggregation stage.
- This is intentional for public release because that stage was a result aggregation helper, not Data Engine core.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- No new step input schemas.
- Removed private aggregation config contract.

### Step Outputs
- Removed private aggregation output contract.

## 6) Config Contract
- Config keys removed from the public surface:
  - private result aggregation stage/config keys
  - final-analysis train/eval config files
  - private serial-plan entry points
- Defaults: unchanged for generic pipeline steps.
- Validation rules: unknown `pipeline.steps` values continue to raise `ValueError`.

## 7) Registry / Dispatch Plan (If applicable)
- Registry name/location: `pipelines/run_yaml_pipeline.py::STAGE_TO_SCRIPT`.
- Removed step registration:
  - private aggregation stage -> private aggregation script.
- Remaining stage names continue resolving to implementation scripts.

## 8) Dependency Direction Check
Confirm imports follow:
Orchestration -> Components -> Core

- Orchestration imports: unchanged (`common.config_io`, stdlib).
- Components imports: unchanged.
- Core imports: unchanged.

## 9) Test Plan (Minimum)
- Unit tests to modify:
  - `test/test_managed_pipeline_smoke.py`
  - `test/test_serial_plan_post_actions.py`
- Integration tests:
  - managed pipeline smoke test.
- How to run tests:
  - `python -m unittest test/test_managed_pipeline_smoke.py test/test_serial_plan_post_actions.py`
  - public-surface scans for private final-analysis references.

## 10) Risks & Mitigations
- Risk: a generic useful eval helper is removed accidentally.
  - Mitigation: only remove private summary helpers and private plan/config/docs, while retaining train/eval execution scripts.
- Risk: old configs remain linked from docs.
  - Mitigation: scan for deleted paths and final-analysis terms after edits.
- Risk: sensitive content remains in git history.
  - Mitigation: document that current-branch cleanup is not history rewriting.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [x] Git commit message: `chore: remove private experiment surface`
- [x] Pushed to remote
