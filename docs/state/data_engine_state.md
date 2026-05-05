# Implementation State (2026-05-05)

## Done
- DataLoader normalization: `ingest/run_dataloader.py`
- Control generation (ComfyUI): `synth/run_generate.py`
- Filter1 (SigLIP2 semantic margin): `filter/filter_stages/filter1/main.py`
- Filter2 (YOLO pose/ROI gate): `filter/filter_stages/filter2/main.py`
- AI annotation for pose labels: `label/run_ai_annotation.py`
- Fair real split builder: `label/build_coco_yolo_pose.py`
- Fair mixed dataset builder: `label/build_mixed_dataset.py`
- YOLO11-pose trainer/eval: `train/run_yolo11_pose.py`, `eval/run_yolo11_pose_eval.py`
- Five-group fair ablation configs under `configs/coco_pose_2017__expansion/{train,eval}/`
- Pose ablation aggregation: `eval/aggregate_pose_ablation_results.py`

## Materialized Artifacts
- Generation:
  - prompt-only synthetic pool: 300 rows
  - prompt+canny synthetic pool: 600 rows
- Filtering:
  - Filter1 input: 900 rows; accepted 732, rejected 168
  - Filter2 input: 732 rows; accepted 647, rejected 16, uncertain 69
- Filtered AI annotation:
  - input 647, annotated 647
  - train samples 518, val samples 129
- Fair real split:
  - real train anchor 1589 images
  - anchor val 280 images
  - shared real holdout 329 images
- Mixed filtered training dataset:
  - 1589 real-train + 518 filtered-synth train = 2107 train images
  - shared real holdout reused for eval

## Not Yet Run / TODO
- Raw synthetic annotation run on pre-filter synth manifest
- Real + raw synthetic mixed dataset materialization
- Full five-group training runs on fair protocol datasets
- Shared-holdout eval runs for all five groups
- Final paper figures / summary table export

## Result Caveat
- Existing `body_pose_coco_train_real_only` and `body_pose_coco_train_synth_only` training reports are legacy/internal-validation runs. They are useful smoke evidence that training works, but they are not the final paper numbers because the fair protocol reports must use `A` through `E` run IDs and shared `real_test_holdout` evaluation.

## See Also
- [ROADMAP.md](../../ROADMAP.md) — ordered next steps
- [docs/data_flow.md](../data_flow.md) — artifact chain
- [docs/body_pose_fair_experiment.md](../body_pose_fair_experiment.md) — fair protocol definition
