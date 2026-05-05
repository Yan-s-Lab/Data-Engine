# Body Pose Fair Experiment Protocol

## Goal
- Test the data-engine hypotheses under a fixed real-data budget.
- Do **not** claim synthetic data replaces real data.
- Report all final pose metrics on one shared real-only holdout.

## Fairness Rule
- `real_train_anchor` is the only real-data training subset reused across groups.
- `real_test_holdout` is frozen and used for every reported evaluation.
- Synthetic-only datasets may keep internal train/val splits for training control.
- Reported paper numbers must come from `real_test_holdout`, not synthetic validation splits.

## Dataset Lineage
- Real anchors and holdout:
  - `label/build_coco_yolo_pose.py`
  - config: `configs/coco_pose_2017__expansion/train/body_pose_real_only_prep.yaml`
  - outputs:
    - `body_pose_coco_real/label/real_train_anchor`
    - `body_pose_coco_real/label/real_test_holdout`
- Filtered synthetic train set:
  - `label/run_ai_annotation.py`
  - config: `configs/coco_pose_2017__expansion/annotation/body_pose_ai_annotation.yaml`
  - output: `body_pose_coco_annotation/label/ai_dataset`
- Raw synthetic train set:
  - `label/run_ai_annotation.py`
  - config: `configs/coco_pose_2017__expansion/annotation/body_pose_ai_annotation_raw.yaml`
  - output: `body_pose_coco_annotation_raw/label/ai_dataset`
- Mixed train sets:
  - `label/build_mixed_dataset.py`
  - configs:
    - `configs/coco_pose_2017__expansion/train/body_pose_mixed_prep.yaml`
    - `configs/coco_pose_2017__expansion/train/body_pose_mixed_raw_prep.yaml`

## Experiment Groups
- `A_real_only`
  - train config: `configs/coco_pose_2017__expansion/train/body_pose_A_real_only.yaml`
- `B_raw_synth_only`
  - train config: `configs/coco_pose_2017__expansion/train/body_pose_B_raw_synth_only.yaml`
- `C_filtered_synth_only`
  - train config: `configs/coco_pose_2017__expansion/train/body_pose_C_filtered_synth_only.yaml`
- `D_real_plus_raw_synth`
  - train config: `configs/coco_pose_2017__expansion/train/body_pose_D_real_plus_raw_synth.yaml`
- `E_real_plus_filtered_synth`
  - train config: `configs/coco_pose_2017__expansion/train/body_pose_E_real_plus_filtered_synth.yaml`

Matching eval configs live under `configs/coco_pose_2017__expansion/eval/` and all target `real_test_holdout`.

## Aggregation
- Eval entry: `eval/run_yolo11_pose_eval.py`
- Summary entry: `eval/aggregate_pose_ablation_results.py`
- Summary config: `configs/coco_pose_2017__expansion/eval/body_pose_ablation_summary.yaml`

The summary table records:
- pose `mAP50`
- pose `mAP50-95`
- box `mAP50`
- real-train image count
- synth-train image count

## Current Status
- Implemented:
  - fair real split builder
  - raw/filtered synthetic dataset configs
  - fair mixed dataset builder
  - five-group train/eval configs
  - ablation result aggregation utility
- Materialized in local artifacts during this session:
  - `real_train_anchor`
  - `real_test_holdout`
  - `real_plus_filtered_synth_dataset`
- Not completed in this session:
  - raw synthetic annotation run
  - full five-group training
  - full shared-holdout evaluation

The remaining items are runtime-heavy execution tasks rather than missing protocol/code support.
