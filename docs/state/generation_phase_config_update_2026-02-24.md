# Generation Phase Config Update (2026-02-24)

## Scope
- Update generation example config for the current `test/test-generation` dataset.
- Change ComfyUI filename prefix strategy to use guide image filename stem.

## Changes
- Added dataloader config:
  - `configs/examples/dataloader_norm_test_generation_yk001.yaml`
  - points to `test/test-generation/yk-001_arm_deltoid_muscle_seg`
  - sets `require_labels: false` for generation-anchor use
- Updated generate config:
  - `configs/examples/comfyui_generate_from_norm_yk001_prompt_canny.yaml`
  - `generate.real_manifest` -> `artifacts/runs/dataloader_norm_test_generation_yk001/dataloader/real_manifest.jsonl`
  - `filename_prefix.template` -> `{anchor_image_stem}_canny`
  - `filename_prefix.dataloader_config` -> new dataloader config above
- Updated runtime behavior in `synth/run_generate.py`:
  - `filename_prefix.template` context now includes:
    - `anchor_image_stem` / `anchor_image_name` (raw image path preferred, fallback to normalized image path)
    - `anchor_image_stem_raw` / `anchor_image_name_raw`
    - `anchor_image_stem_norm` / `anchor_image_name_norm`

## Validation
1. Run dataloader:
```bash
python ingest/run_dataloader.py --config configs/examples/dataloader_norm_test_generation_yk001.yaml
```
2. Run generate:
```bash
python synth/run_generate.py --config configs/examples/comfyui_generate_from_norm_yk001_prompt_canny.yaml
```
