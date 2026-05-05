# DataLoader Norm + Pipeline Smoke Test (2026-02-24)

## Scope
- Repair broken example path in `configs/examples/dataloader_norm_test.yaml`.
- Add runnable smoke tests for DataLoader as pipeline ingress norm stage.

## What Changed
- Updated DataLoader example config paths:
  - `real_dir`: `artifacts/datasets/rawdatasets/real_arm_deltoid`
  - `image_dir`: `artifacts/datasets/rawdatasets/real_arm_deltoid/images`
  - `label_dir`: `artifacts/datasets/rawdatasets/real_arm_deltoid/labels`
- Added `test/test_dataloader_pipeline_smoke.py` with 2 tests:
  - direct CLI smoke: `ingest/run_dataloader.py`
  - dataloader-only pipeline smoke: `pipelines/run_yaml_pipeline.py` with `pipeline.steps=[dataloader]`

## Validation Commands
```bash
python -m unittest discover -s test -p 'test_dataloader_pipeline_smoke.py' -v
python ingest/run_dataloader.py --config configs/examples/dataloader_norm_test.yaml
```

## Review Notes
- Previous failure root cause: example config pointed to non-existing `artifacts/datasets/rawdatasets/images`.
- Dataloader remains valid as mandatory norm ingress stage and can be isolated as a single-step pipeline stage.
