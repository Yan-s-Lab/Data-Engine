# Pipeline 文档重构（2026-02-25）

## Scope
- 只重构文档，不改代码逻辑。
- 目标：
  - 理清当前配置文件入口与用途。
  - 明确当前交付边界仅到 `dataloader -> generation -> filter(phase1)`。
  - 清理文档中的失效路径与旧执行方式。

## Changes
- 重写 `docs/README_PIPELINE_ZH.md`：
  - 将“当前能力边界”前置。
  - 新增“配置文件怎么选”索引表。
  - 用可执行路径替换失效路径（尤其 filter 配置目录）。
  - 增加“已弃用/不再推荐路径”。
- 更新 `docs/filter_quickstart.md`：
  - 统一到 `test/test-filters/configs/filter_compose.yaml`。
  - 移除旧 `artifacts/testfilter/configs/*` 推荐命令。
- 更新 `README.md`：
  - quickstart 命令改为当前可执行配置路径。
- 更新 `configs/examples/README.md`：
  - 明确 managed/active 配置与历史兼容配置的区别。
- 更新 `deploy/pipeline/pipeline_serial_plan.example.yaml` 注释中的旧 filter 路径。

## Result
- 文档主线与当前可运行范围一致。
- 旧路径（`artifacts/testfilter/configs/*`）不再出现在入口文档中。
- 阶段叙述统一为 phase1 为当前交付终点，避免误导到 annotation/train/HITL。
