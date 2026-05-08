# Roadmap

Data Engine provides a config-driven workflow for preparing vision datasets: ingestion, synthetic generation, filtering, annotation, dataset assembly, training, evaluation, and repeatable pipeline execution.

## Current Scope

The repository includes reusable pipeline components and deployment examples for:

- normalizing image collections into manifests and artifact directories
- generating synthetic samples through ComfyUI workflows
- filtering samples with semantic and pose/ROI checks
- preparing YOLO-style training datasets
- running training and evaluation from config files
- operating pipelines through local runners, Docker Compose, or systemd

For running the pipeline, see [docs/pipeline_operations.md](docs/pipeline_operations.md).

## Planned Improvements

- Simplify the example configs so first-time users can run a small end-to-end workflow with minimal setup.
- Document the input and output contract for each pipeline stage.
- Expand smoke tests around managed pipeline execution.
- Improve diagnostics for missing artifacts, unavailable services, and missing model weights.
- Keep generated outputs and task-specific analysis outside version control.

## Entry Points

| Area | Entry |
|---|---|
| Managed pipeline | `pipelines/run_managed_pipeline.py` |
| Serial pipeline plans | `pipelines/run_serial_plan.py` |
| Docker pipeline service | `deploy/pipeline/docker-compose.pipeline.yml` |
| Server service wrapper | `deploy/systemd/dataengine-pipeline.service` |
| Configuration examples | `configs/` |
| Operation guide | `docs/pipeline_operations.md` |
