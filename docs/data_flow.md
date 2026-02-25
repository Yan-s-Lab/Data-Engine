
# Data Flow (MVP)

本文档用于快速说明 MVP 流程与当前落地状态。

## 1. MVP 目标链路

`dataloader(norm) -> control generation -> filter -> annotation <-> HITL -> training -> 产出`

## 2. 当前已稳定链路

`dataloader -> generation -> filter(phase1)`

说明：
- `annotation / HITL / training` 仍在目标态，未并入当前默认主流程。
- 运行细节与配置说明以主索引和 kernel 分文档为准。

## 3. 文档入口

- 主索引：
  - `docs/README_PIPELINE_ZH.md`
- kernel 分文档：
  - `docs/kernels/dataloader_norm.md`
  - `docs/kernels/control_generation.md`
  - `docs/kernels/filter_phase1.md`
- 事实状态：
  - `docs/state/data_engine_state.md`
