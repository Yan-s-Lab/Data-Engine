# DataEngine 三阶段手册（已验证）

当前仓库在示例配置层面，仅保留并推荐以下已验证阶段：
`dataloader -> generate -> filter`

## 1. 先决条件

1. 在仓库根目录执行命令：
```bash
cd /home/yan/StudioSpace/DataEngine
```
2. Python 环境可用（`python --version` 可执行）。
3. ComfyUI 可访问（用于 generate 阶段），默认 `http://127.0.0.1:8188`。

## 2. DataLoader（data norm）

配置文件：`configs/examples/dataloader_norm_test.yaml`

运行：
```bash
python ingest/run_dataloader.py \
  --config configs/examples/dataloader_norm_test.yaml
```

关键产物：
- `artifacts/runs/dataloader_norm_test/dataloader/real_manifest.jsonl`
- `artifacts/runs/dataloader_norm_test/dataloader/report.json`

## 3. Generation（ComfyUI）

配置文件：`configs/examples/comfyui_generate_from_norm_yk001_prompt_canny.yaml`

运行：
```bash
python synth/run_generate.py \
  --config configs/examples/comfyui_generate_from_norm_yk001_prompt_canny.yaml
```

关键产物：
- `artifacts/runs/yk001_prompt_canny_demo/generate/synth_manifest.jsonl`
- `artifacts/runs/yk001_prompt_canny_demo/generate/mixed_manifest.jsonl`
- `artifacts/runs/yk001_prompt_canny_demo/generate/report.json`

## 4. Filter（单模块）

当前已验证的 filter 示例配置位于：
- `artifacts/testfilter/configs/filter_pcs_clip.yaml`
- `artifacts/testfilter/configs/filter_staged_clip.yaml`
- `artifacts/testfilter/configs/filter_compose.yaml`

运行（示例）：
```bash
python filter/run_filter.py \
  --config artifacts/testfilter/configs/filter_compose.yaml
```

关键产物：
- `.../filter/filter_scores.jsonl`
- `.../filter/splits/{accept,reject,uncertain}.jsonl`
- `.../filter/report.json`

## 5. 常见排查

1. `missing real manifest`
- 先确认 dataloader 已成功产出 `real_manifest.jsonl`。

2. `generate.backend=comfyui requires ... workflow to exist`
- 检查 `generate.comfyui.workflow` 路径是否存在且是 API prompt graph。

3. Filter 没有 real anchor
- 检查 input manifest 中是否有 `source=real` 样本。

## 6. OpenPose（本地外部仓库，不纳入本仓库版本管理）

`third_party/openpose/` 在本仓库中故意不跟踪。需要 OpenPose 时，请在本机自行 clone 与构建：

```bash
git clone https://github.com/CMU-Perceptual-Computing-Lab/openpose.git third_party/openpose
cd third_party/openpose
mkdir -p build && cd build
cmake ..
make -j"$(nproc)"
cd ../..
```

构建完成后可使用仓库脚本（已适配 `third_party/openpose` 默认路径）：

```bash
bash third_party/run_openpose_to_control.sh --image /abs/path/to/image.png
```
