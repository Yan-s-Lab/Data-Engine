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

配置文件：`configs/examples/dataloader_norm_test_generation_yk001.yaml`

运行：
```bash
python ingest/run_dataloader.py \
  --config configs/examples/dataloader_norm_test_generation_yk001.yaml
```

关键产物：
- `artifacts/runs/dataloader_norm_test_generation_yk001/dataloader/real_manifest.jsonl`
- `artifacts/runs/dataloader_norm_test_generation_yk001/dataloader/report.json`

## 3. Generation（ComfyUI）

配置文件：`configs/examples/comfyui_generate_from_norm_yk001_prompt_canny.yaml`

运行：
```bash
python synth/run_generate.py \
  --config configs/examples/comfyui_generate_from_norm_yk001_prompt_canny.yaml
```

说明：
- 当前示例将 `generate.comfyui.filename_prefix.template` 设置为 `{anchor_image_stem}_canny`，
  即以引导图（raw 优先，缺失则回退到 manifest 中 image_path）的文件名 stem 作为输出前缀。
- 若需要跳过超大锚图（避免 OOM），可配置：
```yaml
generate:
  comfyui:
    anchor_filter:
      max_long_edge: 1536   # 超过该最长边的 real image 会被直接跳过
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

## 7. 长任务稳定运行（容器 + systemd）

目标：避免 SSH 断开/本地锁屏导致 pipeline 中断，并在机器重启后自动恢复。

### 7.1 托管版 pipeline runner（支持锁/PID/SIGTERM/续跑）

新增入口：
```bash
python pipelines/run_managed_pipeline.py --config <your_config.yaml>
```

特性：
- 单实例锁：`<run_dir>/pipeline/managed.lock`
- PID 文件：`<run_dir>/pipeline/managed.pid`
- 仅在收到 `SIGTERM/SIGINT` 时主动退出（忽略 `SIGHUP`）
- 断点续跑：默认开启 `pipeline.resume_from_artifacts=true`，已有阶段产物会自动跳过

可选配置：
```yaml
pipeline:
  resume_from_artifacts: true
  lock_file: /abs/path/to/managed.lock   # 可选，默认 run_dir/pipeline/managed.lock
  pid_file: /abs/path/to/managed.pid     # 可选，默认 run_dir/pipeline/managed.pid
```

### 7.2 容器化运行（docker compose）

1. 复制环境变量：
```bash
cp deploy/pipeline/.env.example deploy/pipeline/.env
```
2. 根据需要修改 `deploy/pipeline/.env` 里的 `PIPELINE_CONFIG`。
3. 启动：
```bash
docker compose --env-file deploy/pipeline/.env -f deploy/pipeline/docker-compose.pipeline.yml up -d --build
```
4. 查看日志（固定落盘）：
```bash
tail -f artifacts/logs/managed_pipeline.log
```

### 7.3 主机重启后自动恢复（systemd）

安装并启用服务：
```bash
bash deploy/systemd/install_pipeline_service.sh
```

服务文件：
- `deploy/systemd/dataengine-pipeline.service`

常用命令：
```bash
sudo systemctl status dataengine-pipeline.service
sudo systemctl restart dataengine-pipeline.service
sudo systemctl stop dataengine-pipeline.service
```
