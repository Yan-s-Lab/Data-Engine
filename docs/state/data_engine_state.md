# Implementation State

## Public Components

- DataLoader normalization: `ingest/run_dataloader.py`
- Control generation through ComfyUI: `synth/run_generate.py`
- Filter1 SigLIP2 semantic margin: `filter/filter_stages/filter1/main.py`
- Filter2 YOLO pose/ROI gate: `filter/filter_stages/filter2/main.py`
- AI annotation for pose labels: `label/run_ai_annotation.py`
- Dataset conversion and merge helpers: `label/build_coco_yolo_pose.py`, `label/build_mixed_dataset.py`
- Training/evaluation entry points: `train/`, `eval/`
- Managed pipeline runners: `pipelines/run_managed_pipeline.py`, `pipelines/run_serial_plan.py`

## Public-Repo Boundary

The repository tracks reusable engine code, generic configs, tests, and docs.
Generated datasets, local service state, model weights, result tables, project-specific experiment orchestration, and figure-generation scripts are intentionally excluded.

## See Also

- [ROADMAP.md](../../ROADMAP.md) - public project roadmap
- [docs/data_flow.md](../data_flow.md) - artifact chain
