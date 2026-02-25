# Pipeline 串行分阶段编排 v1（2026-02-25）

## Scope
- 提供第一版分阶段编排能力，满足 `dataloader -> generation组 -> filter组` 的表达方式。
- v1 仅支持串行执行，不引入并发调度。
- 保持已有单任务和配置列表模式可用。

## Changes
- 新增串行计划 runner：`pipelines/run_serial_plan.py`
  - 读取 `serial_plan` 配置。
  - 按 `stages[].tasks[]` 顺序执行 `pipelines/run_managed_pipeline.py`。
  - 支持 `continue_on_error`（计划内默认）与命令行覆盖。
  - 任务日志落盘到 `artifacts/logs/{stage}__{task}_{timestamp}.log`。
  - 生成执行摘要 `artifacts/logs/serial_plan_summary_{timestamp}.json`。
- 更新容器入口：`deploy/pipeline/pipeline_entrypoint.sh`
  - 新增 `PIPELINE_SERIAL_PLAN` 模式，优先级高于配置列表/单配置。
- 更新 compose：`deploy/pipeline/docker-compose.pipeline.yml`
  - 新增环境变量透传 `PIPELINE_SERIAL_PLAN`。
- 更新 env 示例：`deploy/pipeline/.env.example`
  - 增加 `PIPELINE_SERIAL_PLAN` 注释项。
- 新增串行计划示例：`deploy/pipeline/pipeline_serial_plan.example.yaml`
- 更新手册：`docs/README_PIPELINE_ZH.md`
  - 增加串行计划模式说明与日志查看命令。

## Validation
```bash
python -m py_compile pipelines/run_serial_plan.py
bash -n deploy/pipeline/pipeline_entrypoint.sh
python pipelines/run_serial_plan.py \
  --plan deploy/pipeline/pipeline_serial_plan.example.yaml \
  --python-bin true \
  --resume true \
  --log-dir artifacts/logs \
  --log-file artifacts/logs/managed_pipeline.log
```
