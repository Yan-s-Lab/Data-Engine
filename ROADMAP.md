# ROADMAP - Data Engine

## Goal

Keep the public repository focused on the reusable Data Engine: configurable ingestion, generation, filtering, labeling, training, evaluation entry points, and deployment examples.

## Current Status

| Stage | Status | Entry |
|---|---|---|
| DataLoader normalization | Ready | `ingest/run_dataloader.py` |
| Control generation | Ready | `synth/run_generate.py` |
| Filter1 SigLIP2 semantic margin | Ready | `filter/filter_stages/filter1/main.py` |
| Filter2 YOLO pose/ROI gate | Ready | `filter/filter_stages/filter2/main.py` |
| AI annotation | Ready | `label/run_ai_annotation.py` |
| Dataset conversion/merge | Ready | `label/build_coco_yolo_pose.py`, `label/build_mixed_dataset.py` |
| Training | Ready | `train/run_train.py`, `train/run_yolo11_pose.py`, `train/run_yolo11_seg.py` |
| Evaluation | Ready | `eval/run_eval.py`, `eval/run_yolo11_pose_eval.py`, `eval/run_yolo11_seg_eval.py` |
| Managed pipeline | Ready | `pipelines/run_managed_pipeline.py`, `pipelines/run_serial_plan.py` |

## Public-Repo Priorities

1. Keep example configs runnable without private data.
2. Keep generated artifacts, local service state, model weights, and experiment results out of git.
3. Improve generic smoke tests for each public pipeline stage.
4. Document required input/output contracts for each stage.
5. Keep project-specific analysis, result aggregation, and figure scripts outside this repository.

## Artifact Policy

Runtime outputs belong under ignored artifact directories such as `artifacts/` or `runs/`.
The public repo should track source code, generic configs, tests, and documentation only.
