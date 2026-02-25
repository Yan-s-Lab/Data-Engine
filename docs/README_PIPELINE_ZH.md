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
- 输出：`synth_manifest.jsonl` + `mixed_manifest.jsonl`

3. `Filter (phase1 now)`
- 输入：`mixed_manifest.jsonl`（推荐）或显式 manifest
- 输出：`filter_scores.jsonl` + `accept/reject/uncertain`

4. `Annotation <-> HITL`（目标态，未并入当前主路径）

5. `Training`（目标态，未并入当前主路径）

## 3. Phase 产物流转关系（主流程）

| Phase | 关键产物 | 下一个 Phase 如何消费 |
| --- | --- | --- |
| DataLoader | `dataloader/real_manifest.jsonl` | Generation 通过 `generate.real_manifest` 读取 |
| Control Generation | `generate/mixed_manifest.jsonl` | Filter 作为主输入 manifest（推荐自动发现） |
| Filter(phase1) | `filter_scores.jsonl` + `splits/*` | 目标态交给 Annotation/HITL/Training（当前未并入默认主路径） |
| Annotation/HITL（目标态） | 清洗标注数据集 | Training 消费 |
| Training（目标态） | 模型与评估产物 | 反馈下轮配置/策略 |

## 4. 分文档索引（前 3 个 kernel）

- DataLoader（norm）：
  [docs/kernels/dataloader_norm.md](/home/yan/StudioSpace/DataEngine/docs/kernels/dataloader_norm.md)
- Control Generation（ComfyUI）：
  [docs/kernels/control_generation.md](/home/yan/StudioSpace/DataEngine/docs/kernels/control_generation.md)
- Filter（phase1）：
  [docs/kernels/filter_phase1.md](/home/yan/StudioSpace/DataEngine/docs/kernels/filter_phase1.md)

兼容入口（历史名称）：
- [docs/filter_quickstart.md](/home/yan/StudioSpace/DataEngine/docs/filter_quickstart.md)

## 5. 运行前准备（入口）

- 快速准备清单见：
  [README.md](/home/yan/StudioSpace/DataEngine/README.md)
  `Prepare Phase (before any run scripts)` 小节。
- 若目标是跑到 generation，请先确保：
  - Python 依赖已安装（`requirements.txt`）
  - ComfyUI 服务可用（`third_party/comfyui/comfyui_ctl.sh check`）
  - dataloader 配置中的输入路径存在（`dataloader.image_dir`/`label_dir`）

## 6. Pipeline 编排入口

- 单配置托管运行：`pipelines/run_managed_pipeline.py`
- 容器入口：`deploy/pipeline/docker-compose.pipeline.yml`
- 串行计划：`deploy/pipeline/pipeline_serial_plan.example.yaml`

`deploy/pipeline/.env` 变量优先级：
`PIPELINE_SERIAL_PLAN` > `PIPELINE_CONFIG_LIST_FILE/PIPELINE_CONFIGS` > `PIPELINE_CONFIG`

## 7. 文档边界规则

- 主文档：只放架构、边界、索引，不展开参数细节。
- 分文档：只放对应 kernel 的技术细节、脚本运行、配置说明、产物和排查。
- 事实状态变更：记录到 `docs/state/*.md`。
