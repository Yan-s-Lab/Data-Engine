# Data Engine

Config-driven data pipeline for building, filtering, labeling, training, and evaluating synthetic-first vision datasets.

**Pipeline**

```text
dataloader(norm) -> control generation -> filter1(SigLIP2) -> filter2(YOLO pose/ROI) -> annotation -> training/eval
```

## Setup

```bash
conda create -n dataengine python=3.10 -y
conda activate dataengine
pip install -r requirements.txt
```

Optional local services:

```bash
./third_party/comfyui/comfyui_ctl.sh ensure
./third_party/label_studio/label_studio_ctl.sh ensure
```

## Run Commands

Normalize input images:

```bash
python ingest/run_dataloader.py \
  --config configs/examples/dataloader_norm_test_generation_yk002.yaml
```

Generate synthetic images through ComfyUI:

```bash
python synth/run_generate.py \
  --config configs/examples/comfyui_generate_from_norm_yk001_prompt_only_managed.yaml
```

Build filter input and run the two filter stages:

```bash
python filter/utils/build_siglip2_input_manifest.py \
  --config configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_input_construction.yaml

python filter/filter_stages/filter1/main.py \
  --config configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline.yaml

python filter/filter_stages/filter2/main.py \
  --config configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline_filter2.yaml
```

Annotate accepted synthetic images:

```bash
python label/run_ai_annotation.py \
  --config configs/coco_pose_2017__expansion/annotation/body_pose_ai_annotation.yaml
```

Train:

```bash
python train/run_yolo11_pose.py \
  --config configs/coco_pose_2017__expansion/train/body_pose_mixed.yaml
```

## Managed Pipeline

Single-node YAML pipelines are resolved by stage name from config:

```bash
python pipelines/run_managed_pipeline.py \
  --config configs/examples/dataloader_norm_test_generation_yk003_managed.yaml
```

For serial multi-task plans:

```bash
python pipelines/run_serial_plan.py \
  --plan configs/coco_pose_2017__expansion/pipeline_serial_plan.yk003.yaml
```

## Key Configs

| Config | Purpose |
|---|---|
| `configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_input_construction.yaml` | Build filter input manifest |
| `configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline.yaml` | Filter1 SigLIP2 semantic margin |
| `configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline_filter2.yaml` | Filter2 YOLO pose/ROI gate |
| `deploy/pipeline/pipeline_serial_plan.example-yk003.yaml` | Docker serial-plan example |

## Docs

- [ROADMAP.md](ROADMAP.md) - public project roadmap
- [docs/data_flow.md](docs/data_flow.md) - pipeline state and artifact flow
- [docs/architecture/style.md](docs/architecture/style.md) - code style rules
- [AGENTS.md](AGENTS.md) - agent execution constraints
