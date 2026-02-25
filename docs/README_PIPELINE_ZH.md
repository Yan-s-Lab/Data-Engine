# DataEngine Pipeline 手册（当前可用范围）

## 1. 当前边界（先看这个）

方法论文路径是五阶段（generation/filter/annotation/train/HITL 闭环），但当前仓库主流程只建议按以下范围使用：

`dataloader -> generation -> filter(phase1)`

不在本手册执行范围内：
- annotation
- training
- HITL 闭环

这些阶段在仓库里仍有历史 stub 或设计稿，但不作为当前主流程交付路径。

## 2. 配置文件怎么选（先理清）

| 目标 | 推荐配置 | 说明 |
| --- | --- | --- |
| DataLoader（本地） | `configs/examples/dataloader_norm_test_generation_yk002.yaml` | 只跑 dataloader，产出 real manifest |
| DataLoader（托管） | `configs/examples/dataloader_norm_test_generation_yk002_managed.yaml` | 给 `run_managed_pipeline.py` / serial plan 用，显式 `pipeline.steps: [dataloader]` |
| Generation（prompt-only） | `configs/examples/comfyui_generate_from_norm_yk001_prompt_only_managed.yaml` | ComfyUI 纯 prompt 路径 |
| Generation（prompt+canny） | `configs/examples/comfyui_generate_from_norm_yk001_prompt_canny_managed.yaml` | ComfyUI 引导图路径 |
| Filter（phase1 路由） | `test/test-filters/configs/filter_compose.yaml` | 当前保留的可运行 filter 配置 |
| 容器入口环境 | `deploy/pipeline/.env.example` | 队列/串行计划入口变量 |
| 串行计划样例 | `deploy/pipeline/pipeline_serial_plan.example.yaml` | v1 串行执行（默认示例是 dataloader + generation） |

## 3. 最小可跑路径（phase1）

先决条件：
- 在仓库根目录：`/home/yan/StudioSpace/DataEngine`
- Python 可用
- ComfyUI API 可访问：`http://127.0.0.1:8188`

### 3.1 DataLoader

```bash
python ingest/run_dataloader.py \
  --config configs/examples/dataloader_norm_test_generation_yk002.yaml
```

关键产物：
- `artifacts/runs/dataloader_norm_test_generation_yk002/dataloader/real_manifest.jsonl`
- `artifacts/runs/dataloader_norm_test_generation_yk002/dataloader/report.json`

### 3.2 Generation（二选一）

prompt-only：
```bash
python synth/run_generate.py \
  --config configs/examples/comfyui_generate_from_norm_yk001_prompt_only_managed.yaml
```

prompt+canny：
```bash
python synth/run_generate.py \
  --config configs/examples/comfyui_generate_from_norm_yk001_prompt_canny_managed.yaml
```

关键产物（run_id 对应配置中的 `run.run_id`）：
- `artifacts/runs/<run_id>/generate/synth_manifest.jsonl`
- `artifacts/runs/<run_id>/generate/mixed_manifest.jsonl`
- `artifacts/runs/<run_id>/generate/report.json`

### 3.3 Filter（phase1）

```bash
python filter/run_filter.py \
  --config test/test-filters/configs/filter_compose.yaml
```

关键产物：
- `test/test-filters/runs/testfilter_compose/filter/filter_scores.jsonl`
- `test/test-filters/runs/testfilter_compose/filter/splits/{accept,reject,uncertain}.jsonl`
- `test/test-filters/runs/testfilter_compose/filter/report.json`

## 4. 托管运行（长任务）

### 4.1 托管 runner

```bash
python pipelines/run_managed_pipeline.py --config <your_config.yaml>
```

特性：
- 单实例锁：`managed.lock`
- PID 文件：`managed.pid`
- 收到 `SIGTERM/SIGINT` 可优雅退出
- `pipeline.resume_from_artifacts=true` 时支持续跑

### 4.2 docker compose

```bash
cp deploy/pipeline/.env.example deploy/pipeline/.env
```

`deploy/pipeline/.env` 优先级：
`PIPELINE_SERIAL_PLAN` > `PIPELINE_CONFIG_LIST_FILE/PIPELINE_CONFIGS` > `PIPELINE_CONFIG`

启动：
```bash
docker compose --env-file deploy/pipeline/.env -f deploy/pipeline/docker-compose.pipeline.yml up -d --build
```

看日志：
```bash
tail -f artifacts/logs/managed_pipeline.log
ls -lt artifacts/logs/*_*.log | head
ls -lt artifacts/logs/serial_plan_summary_*.json | head
```

停止：
```bash
docker compose --env-file deploy/pipeline/.env -f deploy/pipeline/docker-compose.pipeline.yml down
```

### 4.3 systemd（可选）

```bash
bash deploy/systemd/install_pipeline_service.sh
sudo systemctl status dataengine-pipeline.service
```

## 5. 已弃用/不再推荐路径

- `artifacts/testfilter/configs/*`：已不作为配置来源（路径已迁移到 `test/test-filters/configs/`）。
- `configs/examples/dataloader_norm_test_generation_yk001.yaml`：已删除。
- 文档中的全链路 `dataloader -> generate -> filter -> train -> eval` 旧示例：不再作为当前交付路径。

## 6. 常见排查

1. `missing real manifest`
- 先确认 dataloader 已产出 `real_manifest.jsonl`。

2. `generate.backend=comfyui requires ... workflow to exist`
- 检查 `generate.comfyui.workflow` 是否存在且是 API prompt graph。

3. Filter 报 real anchor 不足
- 检查输入 manifest 是否包含 `source=real` 样本。
