# DataEngine 文档主索引（MVP）

## 1. MVP 核心流水线

目标闭环定义：

`dataloader(norm) -> control generation -> filter -> annotation <-> HITL -> training -> 产出`

当前实现状态（2026-02-25）：
- 已稳定：`dataloader -> control generation -> filter(phase1)`
- 未完成到主流程：`annotation / HITL / training`

本主文档负责：
- 架构边界
- kernel 编排关系
- 分文档索引

具体脚本/配置/运行细节放在各 kernel 分文档。

## 2. Kernel 编排视图

1. `DataLoader (norm)`
- 输入：raw real images（可选 label）
- 输出：`real_manifest.jsonl`

2. `Control Generation`
- 输入：real manifest + ComfyUI workflow + prompt/control 配置
- 输出：`synth_manifest.jsonl`

3. `Filter (phase1 now)`
- 输入：`synth_manifest.jsonl`（推荐）或显式 manifest
- 输出：`filter_scores.jsonl` + `accept/reject/uncertain`
- 约束：当前仅支持 `filter.mode=compose`（phase1 v1 极简路径）

4. `Annotation <-> HITL`（目标态，未并入当前主路径）

5. `Training`（目标态，未并入当前主路径）

## 3. Phase 产物流转关系（主流程）

| Phase | 关键产物 | 下一个 Phase 如何消费 |
| --- | --- | --- |
| DataLoader | `dataloader/real_manifest.jsonl` | Generation 通过 `generate.real_manifest` 读取 |
| Control Generation | `generate/synth_manifest.jsonl` | Filter 作为主输入 manifest（推荐自动发现） |
| Filter(phase1) | `filter_scores.jsonl` + `splits/*` | 目标态交给 Annotation/HITL/Training（当前未并入默认主路径） |
| Annotation/HITL（目标态） | 清洗标注数据集 | Training 消费 |
| Training（目标态） | 模型与评估产物 | 反馈下轮配置/策略 |

## 4. 分文档索引（前 3 个 kernel）

- DataLoader（norm）：
  [docs/kernels/dataloader_norm.md](./kernels/dataloader_norm.md)
- Control Generation（ComfyUI）：
  [docs/kernels/control_generation.md](./kernels/control_generation.md)
- Filter（phase1）：
  [docs/kernels/filter_phase1.md](./kernels/filter_phase1.md)

兼容入口（历史名称）：
- [docs/filter_quickstart.md](./filter_quickstart.md)

## 5. 运行前准备（入口）

- 快速准备清单见：
  [README.md](./README.md)
  `Prepare Phase (before any run scripts)` 小节。
- 若目标是跑到 generation，请先确保：
  - Python 依赖已安装（`requirements.txt`）
  - ComfyUI 服务可用（`third_party/comfyui/comfyui_ctl.sh check`）
  - dataloader 配置中的输入路径存在（`dataloader.image_dir`/`label_dir`）

## 6. Pipeline 编排入口

- 单配置托管运行：`pipelines/run_managed_pipeline.py`
- 容器入口：`deploy/pipeline/docker-compose.pipeline.yml`
- 串行计划：`deploy/pipeline/pipeline_serial_plan.example-yk003.yaml`

`deploy/pipeline/.env` 变量优先级：
`PIPELINE_SERIAL_PLAN` > `PIPELINE_CONFIG_LIST_FILE/PIPELINE_CONFIGS` > `PIPELINE_CONFIG`

### 6.1 仅运行 Filter phase1（推荐最简）

若只想跑 filter，请在配置中显式设置：

```yaml
pipeline:
  steps: [filter]
```

并保证 `filter.mode=compose`。

可直接使用 smoke config：

```bash
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
```

## 7. Docker 容器编排 Demo（启动 / 终止 / 重启）

在仓库根目录执行以下命令。

1. 准备配置（首次）

```bash
cp deploy/pipeline/.env.example deploy/pipeline/.env
```

按需编辑 `deploy/pipeline/.env`（三选一）：
- 单配置：设置 `PIPELINE_CONFIG=...`
- 多配置队列：设置 `PIPELINE_CONFIGS=cfg1,cfg2,...` 或 `PIPELINE_CONFIG_LIST_FILE=...`
- 串行分阶段计划：设置 `PIPELINE_SERIAL_PLAN=deploy/pipeline/pipeline_serial_plan.example-yk003.yaml`

2. 启动（前台）

```bash
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml \
  up --build --remove-orphans
```

仅跑 filter 时，建议在 `deploy/pipeline/.env` 指向一个含 `pipeline.steps: [filter]` 的配置文件：
- `PIPELINE_CONFIG=...`
或使用串行计划：
- `PIPELINE_SERIAL_PLAN=deploy/pipeline/pipeline_serial_plan.example-yk003.yaml`

3. 启动（后台）

```bash
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml \
  up --build -d --remove-orphans
```

4. 查看状态与日志

```bash
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml \
  ps
```

```bash
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml \
  logs -f --tail 200
```

补充：查看文件日志（容器内流程会把任务日志落到宿主机 `artifacts/logs/`）

```bash
ls -lt artifacts/logs
tail -n 200 artifacts/logs/managed_pipeline.log
```

补充：查看“当前跑到哪个 phase / 卡在哪个 phase”

```bash
# 1) 先看容器是否在运行或重启
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml \
  ps

# 2) 看最近一次串行计划摘要（status + 每个 stage/task 的 return_code）
ls -t artifacts/logs/serial_plan_summary_*.json | head -n 1 | xargs cat

# 3) 按摘要中的 log 字段打开对应任务日志
tail -n 200 artifacts/logs/dataloader__*.log
tail -n 200 artifacts/logs/generation__*.log
```

5. 终止（停止并移除容器）

```bash
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml \
  down
```

6. 重启（仅重启容器进程）

```bash
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml \
  restart
```

7. 重启（按最新配置重建并启动）

```bash
docker compose --env-file deploy/pipeline/.env \
  -f deploy/pipeline/docker-compose.pipeline.yml \
  up --build -d --force-recreate --remove-orphans
```

可选：若已安装 systemd 服务（`deploy/systemd/dataengine-pipeline.service`），可用：

```bash
sudo systemctl restart dataengine-pipeline.service
sudo systemctl stop dataengine-pipeline.service
sudo systemctl start dataengine-pipeline.service
```

## 8. 文档边界规则

- 主文档：只放架构、边界、索引，不展开参数细节。
- 分文档：只放对应 kernel 的技术细节、脚本运行、配置说明、产物和排查。
- 事实状态变更：记录到 `docs/state/*.md`。
