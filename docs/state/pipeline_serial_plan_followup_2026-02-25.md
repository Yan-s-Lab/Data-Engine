# Pipeline 串行计划跟进修复（2026-02-25）

## Issue
- `deploy/pipeline/pipeline_serial_plan.example.yaml` 中 dataloader 任务使用了普通 dataloader 配置。
- 该配置未显式声明 `pipeline.steps`，会触发 `run_managed_pipeline.py` 默认阶段链，导致任务 1 继续进入 generate/filter/train/eval，而不是仅执行 dataloader。

## Fix
- 新增 dataloader-only 托管配置：
  - `configs/examples/dataloader_norm_test_generation_yk002_managed.yaml`
  - 明确 `pipeline.steps: [dataloader]`
  - 明确 `pipeline.resume_from_artifacts: true`
- 更新串行计划示例：
  - `deploy/pipeline/pipeline_serial_plan.example.yaml`
  - dataloader 节点改为引用 `*_managed.yaml`
- 更新文档提示：
  - `docs/README_PIPELINE_ZH.md`

## Validation
- `pipeline_serial_plan.example.yaml` 结构检查通过。
- 修复后 dataloader 节点将只执行 `dataloader` 阶段，不再串入 generate。
