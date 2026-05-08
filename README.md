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

## Run The Pipeline

Data Engine is designed to run from pipeline configs. Use the managed runner for one config, the serial runner for ordered multi-config jobs, and Docker/systemd for background server runs.

Run one managed config locally:

```bash
python pipelines/run_managed_pipeline.py \
  --config configs/examples/dataloader_norm_test_generation_yk003_managed.yaml \
  --resume true
```

Run an ordered serial plan locally:

```bash
python pipelines/run_serial_plan.py \
  --plan configs/coco_pose_2017__expansion/pipeline_serial_plan.yk003.yaml \
  --resume true \
  --log-dir artifacts/logs \
  --log-file artifacts/logs/serial_plan.log
```

Run the pipeline with Docker Compose:

```bash
cp deploy/pipeline/.env.example deploy/pipeline/.env

PIPELINE_SERIAL_PLAN=configs/coco_pose_2017__expansion/pipeline_serial_plan.yk003.yaml \
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml up --build
```

Run detached in the background:

```bash
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml up --build -d
```

Follow logs:

```bash
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml logs -f
```

For server deployment, use the provided systemd wrapper:

```bash
sudo deploy/systemd/install_pipeline_service.sh
sudo systemctl enable --now dataengine-pipeline
sudo journalctl -u dataengine-pipeline -f
```

See [docs/pipeline_operations.md](docs/pipeline_operations.md) for modes, environment variables, log locations, and shutdown commands.

## Config Model

Pipeline stage order lives in config:

```yaml
pipeline:
  steps: [dataloader, generate, filter]
  resume_from_artifacts: true
```

Stage names are resolved by the managed pipeline registry. Runtime outputs and logs are written under the configured artifact root, which should stay out of git.

## Manual Stage Debugging

Per-stage scripts remain available for local debugging:

```bash
python ingest/run_dataloader.py --config configs/examples/dataloader_norm_test_generation_yk002.yaml
python synth/run_generate.py --config configs/examples/comfyui_generate_from_norm_yk001_prompt_only_managed.yaml
python filter/filter_stages/filter1/main.py --config configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline.yaml
python filter/filter_stages/filter2/main.py --config configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline_filter2.yaml
python label/run_ai_annotation.py --config configs/coco_pose_2017__expansion/annotation/body_pose_ai_annotation.yaml
python train/run_yolo11_pose.py --config configs/coco_pose_2017__expansion/train/body_pose_mixed.yaml
```

Use managed/serial pipeline entry points for regular runs so ordering, resume behavior, and logs are reproducible.

## Key Files

| Path | Purpose |
|---|---|
| `pipelines/run_managed_pipeline.py` | Managed single-config pipeline runner |
| `pipelines/run_serial_plan.py` | Ordered multi-config serial runner |
| `deploy/pipeline/docker-compose.pipeline.yml` | Containerized pipeline service |
| `deploy/pipeline/.env.example` | Pipeline environment template |
| `deploy/systemd/dataengine-pipeline.service` | Server background service wrapper |
| `configs/coco_pose_2017__expansion/pipeline_serial_plan.yk003.yaml` | Public serial-plan example |

## Docs

- [docs/pipeline_operations.md](docs/pipeline_operations.md) - pipeline and background operation
- [ROADMAP.md](ROADMAP.md) - public project roadmap
- [docs/data_flow.md](docs/data_flow.md) - pipeline state and artifact flow
- [docs/architecture/style.md](docs/architecture/style.md) - architecture and contribution style
