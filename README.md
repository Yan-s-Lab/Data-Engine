# CLI Rewrite Quickstart

This branch is the CLI-first rewrite scaffold.

## 中文手册（傻瓜式）
- `docs/README_PIPELINE_ZH.md`

## Verified examples in `configs/examples`

1. Normalize raw real data (DataLoader):
```bash
python ingest/run_dataloader.py \
  --config configs/examples/dataloader_norm_test_generation_yk002.yaml
```

2. Generate synthetic data from normalized manifest (ComfyUI backend, prompt-only):
```bash
python synth/run_generate.py \
  --config configs/examples/comfyui_generate_from_norm_yk001_prompt_only_managed.yaml
```

3. Filter phase1 stage smoke test:
```bash
python filter/run_filter.py \
  --config test/test-filters/configs/filter_compose.yaml
```

## OpenPose (local external clone)

`third_party/openpose/` is intentionally not tracked by this repository.
If you need OpenPose tools, clone and build it locally:

```bash
git clone https://github.com/CMU-Perceptual-Computing-Lab/openpose.git third_party/openpose
cd third_party/openpose
mkdir -p build && cd build
cmake ..
make -j"$(nproc)"
cd ../..
```

Then run helper script:

```bash
bash third_party/run_openpose_to_control.sh --image /abs/path/to/image.png
```
