# CLI Rewrite Quickstart

This branch is the CLI-first rewrite scaffold.

## 中文手册（傻瓜式）
- `docs/README_PIPELINE_ZH.md`

## Verified examples in `configs/examples`

1. Normalize raw real data (DataLoader):
```bash
python ingest/run_dataloader.py \
  --config configs/examples/dataloader_norm_test.yaml
```

2. Generate synthetic data from normalized manifest (ComfyUI backend):
```bash
python synth/run_generate.py \
  --config configs/examples/comfyui_generate_from_norm_yk001_prompt_canny.yaml
```

3. Filter stage smoke test:
```bash
python filter/run_filter.py \
  --config artifacts/testfilter/configs/filter_compose.yaml
```
