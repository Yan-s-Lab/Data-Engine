# Pipeline Operations

Data Engine is meant to run from config-driven pipeline entry points. Stage scripts are still available for development and debugging, but production-style runs should use the managed runner, serial runner, Docker Compose, or systemd service.

## Modes

| Mode | Entry | Use when |
|---|---|---|
| Managed config | `pipelines/run_managed_pipeline.py` | Running one config with `pipeline.steps` |
| Serial plan | `pipelines/run_serial_plan.py` | Running several configs in an ordered plan |
| Docker Compose | `deploy/pipeline/docker-compose.pipeline.yml` | Running the pipeline in a container |
| systemd | `deploy/systemd/dataengine-pipeline.service` | Keeping the Docker pipeline running on a server |

## Managed Config

Run one config locally:

```bash
python pipelines/run_managed_pipeline.py \
  --config configs/examples/dataloader_norm_test_generation_yk003_managed.yaml \
  --resume true
```

The config owns the stage order:

```yaml
pipeline:
  steps: [dataloader, generate, filter]
  resume_from_artifacts: true
```

The runner resolves stage names through `pipelines/run_yaml_pipeline.py::STAGE_TO_SCRIPT`, writes a runtime config snapshot, and skips completed stages when resume is enabled.

## Serial Plan

Run an ordered multi-task plan locally:

```bash
python pipelines/run_serial_plan.py \
  --plan configs/coco_pose_2017__expansion/pipeline_serial_plan.yk003.yaml \
  --resume true \
  --log-dir artifacts/logs \
  --log-file artifacts/logs/serial_plan.log
```

Serial plans are useful when a run needs multiple configs, service cleanup after tasks, or explicit task ordering.

## Docker Compose

Create a local environment file:

```bash
cp deploy/pipeline/.env.example deploy/pipeline/.env
```

Run one config:

```bash
PIPELINE_CONFIG=configs/examples/dataloader_norm_test_generation_yk003_managed.yaml \
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml up --build
```

Run a serial plan:

```bash
PIPELINE_SERIAL_PLAN=configs/coco_pose_2017__expansion/pipeline_serial_plan.yk003.yaml \
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml up --build
```

For long-running server jobs, run detached:

```bash
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml up --build -d
```

Inspect logs:

```bash
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml logs -f
```

Stop the pipeline:

```bash
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml down
```

## Environment Variables

| Variable | Purpose |
|---|---|
| `PIPELINE_CONFIG` | Single managed config path |
| `PIPELINE_CONFIGS` | Comma-separated managed config queue |
| `PIPELINE_CONFIG_LIST_FILE` | File with one config path per line |
| `PIPELINE_SERIAL_PLAN` | Serial plan path; takes priority over config queue variables |
| `PIPELINE_RESUME` | Resume completed artifacts; default `true` |
| `PIPELINE_CONTINUE_ON_ERROR` | Continue queue after failures; default `false` |
| `PIPELINE_LOG_DIR` | Log directory; default `/workspace/artifacts/logs` in Docker |
| `PIPELINE_LOG_FILE` | Controller log path |

## systemd Service

The systemd unit wraps Docker Compose for server use:

```bash
sudo deploy/systemd/install_pipeline_service.sh
sudo systemctl enable --now dataengine-pipeline
sudo journalctl -u dataengine-pipeline -f
```

Before enabling it, edit `deploy/pipeline/.env` and verify `WorkingDirectory` in `deploy/systemd/dataengine-pipeline.service` matches the repository path on the server.

## Manual Stage Scripts

Manual scripts are useful for debugging a single stage:

```bash
python ingest/run_dataloader.py --config <config>
python synth/run_generate.py --config <config>
python filter/filter_stages/filter1/main.py --config <config>
python filter/filter_stages/filter2/main.py --config <config>
python label/run_ai_annotation.py --config <config>
python train/run_yolo11_pose.py --config <config>
```

Prefer pipeline configs for regular runs so stage order, resume behavior, and logs are reproducible.
