# CLI Rewrite Quickstart

This branch is the CLI-first rewrite scaffold.

## Prepare Phase (before any run scripts)

1. Python environment (`>=3.10`, recommended: conda + pip):
```bash
conda create -n dataengine python=3.10 -y
conda activate dataengine
pip install -U pip
pip install -r requirements.txt
```

Optional fallback (if you do not use conda):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

2. Runtime dependencies for generation (ComfyUI backend):
- Docker + Docker Compose
- NVIDIA driver + `nvidia-container-toolkit` (GPU mode)

3. Start or verify ComfyUI service:
```bash
./third_party/comfyui/comfyui_ctl.sh ensure
./third_party/comfyui/comfyui_ctl.sh check
```

```bash
# Give your current account permission for changging volume of docker: data/comfyui
sudo chown -R "$USER":"$USER" data/comfyui
```

```bash
# Download example models, it can be quite of big. you can modify `.third_party/comfyui/models.yaml` based on yourself task.
# For example, Comment out unused model combinations. 
# For more details, please look at your ComfyUI UI Services: 127.0.0.1:8188
./third_party/comfyui/download_models.sh  

```

4. Ensure dataset paths in your dataloader config exist before running:
- `dataloader.image_dir`
- `dataloader.label_dir` (if labels are required)

## 中文手册（傻瓜式）
- `docs/README_PIPELINE_ZH.md`

## Kernel Docs
- `docs/kernels/dataloader_norm.md`
- `docs/kernels/control_generation.md`
- `docs/kernels/filter_phase1.md`

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
