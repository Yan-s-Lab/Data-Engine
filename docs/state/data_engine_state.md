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

## Not Yet Run / TODO
- Raw synthetic annotation run on pre-filter synth manifest
- Full five-group training runs on fair protocol datasets
- Shared-holdout eval runs for all five groups
- Final paper figures / summary table export

## See Also
- [ROADMAP.md](../../ROADMAP.md) — ordered next steps
- [docs/data_flow.md](../data_flow.md) — artifact chain
- [docs/body_pose_fair_experiment.md](../body_pose_fair_experiment.md) — fair protocol definition
