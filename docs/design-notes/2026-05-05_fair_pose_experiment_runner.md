## 1) Summary
- Add a one-command fair pose experiment runner that executes the existing raw annotation, mixed dataset, five training groups, shared-holdout eval, and aggregation tasks.
- Keep workflow ordering in a serial-plan YAML while providing a thin shell wrapper for convenience.

## 2) Scope
### In scope
- Extend the managed pipeline stage registry to cover existing experiment scripts.
- Add `pipeline.steps` to fair-protocol configs so each task is explicitly config-driven.
- Add a serial plan for the fair pose ablation experiment.
- Add a thin shell wrapper that invokes the serial plan.
- Add/update lightweight tests for stage registry output checks.

### Out of scope
- Changing generation, filtering, AI annotation, model training, or eval algorithms.
- Running long GPU jobs as part of unit tests.

## 3) Layer Placement (Orchestration / Components / Core)
- Orchestration:
  - `pipelines/run_yaml_pipeline.py`
  - `configs/coco_pose_2017__expansion/...`
  - `scripts/run_body_pose_fair_experiment.sh`
- No component/core changes are needed because the runner only composes existing entry scripts.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `pipelines/run_managed_pipeline.py --config <config> --resume <bool>`
  - Existing CLI retained.
  - `pipeline.steps` may now include:
    - `coco_to_yolo_pose`
    - `annotation`
    - `build_mixed`
    - `train_yolo_pose`
    - `eval_yolo_pose`
    - `aggregate_pose_ablation`
- `pipelines/run_serial_plan.py --plan <plan> --resume <bool>`
  - Existing CLI retained.
- `scripts/run_body_pose_fair_experiment.sh [plan]`
  - Optional first arg overrides the default fair ablation plan.

### Backward compatibility
- Existing stage names remain supported.
- Existing configs without `pipeline.steps` keep the previous default behavior.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Serial plan:
  - `serial_plan.stages[].tasks[].config`: config path for one managed-pipeline task.
- Per-task configs:
  - `pipeline.steps`: one existing stage name.
  - Existing stage-specific sections remain unchanged (`annotation`, `build_mixed`, `train_yolo`, `eval_yolo`, `aggregate_pose_ablation`, `coco_to_yolo_pose`).

### Step Outputs
- `coco_to_yolo_pose`: `label/real_split_report.json`
- `annotation`: `label/ai_annotation_report.json`, `label/ai_dataset/dataset.yaml`
- `build_mixed`: `label/<output_name>/report.json`, `label/<output_name>/dataset.yaml`
- `train_yolo_pose`: `train_yolo_pose/report.json`, checkpoint under `runs/pose/.../weights/best.pt`
- `eval_yolo_pose`: `eval_yolo_pose/report.json`
- `aggregate_pose_ablation`: `pose_ablation_summary/summary.json`, `.csv`, `.md`

## 6) Config Contract
- Config keys used:
  - `pipeline.steps`
  - `pipeline.resume_from_artifacts`
  - `build_mixed.output_name`
- Defaults:
  - legacy pipeline defaults remain unchanged when `pipeline.steps` is absent.
  - `build_mixed.output_name` defaults to `mixed_dataset`.
- Validation rules:
  - unknown `pipeline.steps` entries fail in the managed runner.
  - stage output checks must find each stage's expected artifact before marking a task complete.

## 7) Registry / Dispatch Plan
- Registry: `pipelines/run_yaml_pipeline.py::STAGE_TO_SCRIPT`
- New stage names map to existing entry scripts:
  - `coco_to_yolo_pose` -> `label/build_coco_yolo_pose.py`
  - `annotation` -> `label/run_ai_annotation.py`
  - `build_mixed` -> `label/build_mixed_dataset.py`
  - `train_yolo_pose` -> `train/run_yolo11_pose.py`
  - `eval_yolo_pose` -> `eval/run_yolo11_pose_eval.py`
  - `aggregate_pose_ablation` -> `eval/aggregate_pose_ablation_results.py`

## 8) Dependency Direction Check
Confirm imports follow:
Orchestration -> Components -> Core

- Orchestration imports:
  - pipeline runners import `common.config_io`
- Components imports:
  - unchanged
- Core imports:
  - unchanged

## 9) Test Plan (Minimum)
- Unit tests to add/modify:
  - managed pipeline output checks for new experiment stages.
  - serial plan parsing for the fair experiment plan.
- Integration test to add/modify:
  - no long-running GPU integration test; existing managed smoke test remains.
- How to run tests:
  - `conda run -n dataengine python -m unittest test/test_managed_pipeline_smoke.py test/test_serial_plan_post_actions.py`

## 10) Risks & Mitigations
- Risk: one-command runner accidentally reruns expensive completed stages.
- Mitigation: keep `resume_from_artifacts: true` and stage-specific artifact checks.
- Risk: raw and filtered branches use different candidate pools.
- Mitigation: the serial plan keeps raw annotation explicit and visible; candidate-pool matching remains a protocol review item before final paper claims.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [x] Code changes implemented
- [x] Tests added/updated
- [x] Docs updated
- [x] Git commit message: `feat(exp): add fair pose experiment runner`
- [x] Pushed to remote
