## 1) Summary
- Add a fair pose-experiment protocol for the body-pose paper under a fixed real-data budget.
- Freeze one shared real-only holdout for reported metrics, add raw/filtered synthetic dataset branches, and build mixed datasets that reuse the shared real holdout instead of synthetic validation splits.

## 2) Scope
### In scope
- Extend real-data preparation to emit `real_train_anchor` and `real_test_holdout`.
- Add raw-synthetic annotation config alongside the existing filtered-synthetic annotation branch.
- Update mixed dataset construction to merge only training samples while reusing the shared real holdout as eval split.
- Add train/eval configs for five ablation groups.
- Add a result aggregation utility and experiment protocol docs.
- Add unit tests for deterministic real split construction and fair mixed dataset assembly.

### Out of scope
- Changing the underlying pose model family or hyperparameters.
- Redesigning the filtering stages or AI annotation model.
- Introducing a new orchestrator for end-to-end scheduling beyond script/config support.

## 3) Layer Placement (Orchestration / Components / Core)
- Orchestration:
  - `label/build_coco_yolo_pose.py`
  - `label/build_mixed_dataset.py`
  - `eval/run_yolo11_pose_eval.py`
  - new experiment result aggregation script under `eval/`
  - ablation configs under `configs/coco_pose_2017__expansion/`
- Documentation/testing:
  - protocol docs under `docs/`
  - unit tests under `test/`
- Why this placement:
  - dataset preparation and evaluation wiring are entry-style data orchestration tasks driven by config.
  - no model/runtime algorithm changes require a new core library abstraction for this scope.

## 4) Interfaces (Signatures)
### New/changed public interfaces
- `label/build_coco_yolo_pose.py --config <path>`
  - config adds support for `test_ratio` or `test_count`, plus optional dataset subdirectory naming.
- `label/build_mixed_dataset.py --config <path>`
  - config changes from `{real_dataset, synth_dataset}` to explicit roots for real-train, shared-real-holdout, and synth-train input.
- `eval/run_yolo11_pose_eval.py --config <path>`
  - existing interface retained; new configs standardize `eval_yolo.dataset_yaml`, `checkpoint`, and `split`.
- `eval/aggregate_pose_ablation_results.py --config <path>`
  - reads per-group train reports and eval reports, emits one compact metrics table.

### Backward compatibility
- Existing raw scripts remain callable with legacy config keys where feasible.
- Existing `real_dataset`/`mixed_dataset` artifact roots stay valid; new fair-protocol runs use new run IDs and subdirectories to avoid breaking older artifacts.

## 5) Data Contracts (Explicit Schemas)
### Step Inputs
- Real dataset prep config:
  - required: `annotation_json`, `images_dir`
  - required fairness split fields: either `test_ratio` or `test_count`
  - optional: `val_ratio` for internal train/val split inside `real_train_anchor`
- Synthetic annotation config:
  - required: `input_manifest`, `model`, `device`
- Mixed dataset config:
  - required: `real_train_dataset`, `shared_eval_dataset`, `synth_train_dataset`

### Step Outputs
- `real_train_anchor/`
  - YOLO pose dataset with `images/train`, optional `images/val`, matching labels, and `dataset.yaml`
- `real_test_holdout/`
  - YOLO pose dataset rooted at `images/test` / `labels/test` and a `dataset.yaml` exposing the frozen benchmark split
- `raw_synth_dataset/`, `filtered_synth_dataset/`
  - YOLO pose datasets produced by the same annotation path
- Mixed datasets:
  - merged `images/train` + `labels/train`
  - `dataset.yaml` whose evaluation split points to the shared real holdout
- Aggregation report:
  - per-group metrics: pose `mAP50`, pose `mAP50-95`, box `mAP50`, real-train count, synth-train count

## 6) Config Contract
- Real prep config keys:
  - `coco_to_yolo_pose.output_name`
  - `coco_to_yolo_pose.test_ratio` or `coco_to_yolo_pose.test_count`
  - `coco_to_yolo_pose.anchor_val_ratio`
- Mixed prep config keys:
  - `build_mixed.output_name`
  - `build_mixed.real_train_dataset`
  - `build_mixed.shared_eval_dataset`
  - `build_mixed.synth_train_dataset`
- Eval config keys:
  - `eval_yolo.dataset_yaml`
  - `eval_yolo.checkpoint`
  - `eval_yolo.split`
- Aggregation config keys:
  - ablation group ids and report paths

## 7) Registry / Dispatch Plan (If applicable)
- Not applicable. The protocol is script/config driven and does not add a new step registry.

## 8) Dependency Direction Check
Confirm imports follow:
Orchestration → Components → Core

- Orchestration imports:
  - label/eval scripts import `common.config_io` and `common.manifest_io`.
- Components imports:
  - none added.
- Core imports:
  - none added.

## 9) Test Plan (Minimum)
- Unit tests to add/modify:
  - deterministic real split builder with train/holdout separation and dataset YAML checks
  - mixed dataset builder copies only training samples and reuses shared eval split
  - aggregation utility produces the expected compact result table from mock reports
- Integration test to add/modify:
  - smoke test raw vs filtered annotation configs resolve valid input manifests and output dataset paths without running model inference
- How to run tests:
  - `conda run -n dataengine python -m unittest test/test_build_coco_yolo_pose.py`
  - `conda run -n dataengine python -m unittest test/test_build_mixed_dataset.py`
  - `conda run -n dataengine python -m unittest test/test_aggregate_pose_ablation_results.py`

## 10) Risks & Mitigations
- Risk: old mixed dataset behavior leaked synthetic validation into reported metrics.
- Mitigation: mixed builder now takes a mandatory shared real eval dataset and never merges synth eval assets into the benchmark.
- Risk: users may still point final eval at synthetic dataset YAMLs.
- Mitigation: add explicit eval configs per group that all target the same frozen holdout.
- Risk: large training/eval jobs may exceed local session time.
- Mitigation: implement all scripts/configs and run lightweight validation immediately; leave long-running experiment execution resumable by config.

## 11) Implementation Checklist
- [x] Design note approved/ready
- [ ] Code changes implemented
- [ ] Tests added/updated
- [ ] Docs updated
- [ ] Git commit message: `feat(exp): add frozen real holdout split for fair pose evaluation`
- [ ] Pushed to remote
