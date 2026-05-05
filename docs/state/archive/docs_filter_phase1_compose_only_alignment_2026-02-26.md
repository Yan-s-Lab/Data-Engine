# 文档对齐：Filter phase1 compose-only 运行与 Docker 指南（2026-02-26）

## Scope
- 对齐入口文档，确保运行说明与当前代码一致。
- 不修改算法与 pipeline 代码行为。

## Changes
- `README.md`
  - 明确 filter 当前仅支持 `filter.mode=compose`。
  - 补充 managed pipeline/docker 场景需显式 `pipeline.steps: [filter]`。

- `docs/README_PIPELINE_ZH.md`
  - 在 Filter 编排说明中新增 compose-only 约束。
  - 新增“仅运行 Filter phase1（推荐最简）”说明与运行命令。
  - 在 Docker 启动段补充 filter-only 配置建议。

- `docs/filter_quickstart.md`
  - 补充 compose-only 约束与最简运行命令。

- `configs/examples/README.md`
  - 补充 Filter 示例配置为 compose-only 的说明。

## Validation
- 文档路径与命令已与当前代码对齐：
  - `filter/run_filter.py` 仅支持 `filter.mode=compose`
  - 推荐命令：
    `python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml`
