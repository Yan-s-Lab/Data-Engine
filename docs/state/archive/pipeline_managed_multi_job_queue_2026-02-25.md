# Pipeline 托管容器多任务队列（2026-02-25）

## Scope
- 在现有托管容器入口上支持多任务编排（串行队列）。
- 兼容现有单任务 `PIPELINE_CONFIG` 运行方式。
- 增加总控日志与任务日志分离，便于夜间批量生成追踪。

## Changes
- 更新 `deploy/pipeline/pipeline_entrypoint.sh`：
  - 新增多任务配置来源：
    - `PIPELINE_CONFIGS`（逗号分隔）
    - `PIPELINE_CONFIG_LIST_FILE`（每行一个配置，支持 `#` 注释）
  - 单任务兼容：未提供多任务变量时继续使用 `PIPELINE_CONFIG`。
  - 队列串行执行 `pipelines/run_managed_pipeline.py`。
  - 日志策略：
    - 总控日志：`PIPELINE_LOG_FILE`
    - 每任务日志：`${PIPELINE_LOG_DIR}/{config_basename}_{timestamp}.log`
  - 新增失败策略：`PIPELINE_CONTINUE_ON_ERROR`。
- 更新 `deploy/pipeline/docker-compose.pipeline.yml`：
  - 透传新环境变量 `PIPELINE_CONFIGS`、`PIPELINE_CONFIG_LIST_FILE`、`PIPELINE_CONTINUE_ON_ERROR`。
- 更新 `deploy/pipeline/.env.example`：
  - 增加多任务示例配置和失败策略说明。
- 新增 `deploy/pipeline/pipeline_configs.example.txt`：
  - 给出 `prompt_only` + `prompt_canny` 两个 generation 配置的队列示例。
- 更新 `docs/README_PIPELINE_ZH.md`：
  - 增加多任务配置方式（CSV / 文件）与日志查看方法。

## Validation
- 语法校验：
```bash
bash -n deploy/pipeline/pipeline_entrypoint.sh
```

## Notes
- 入口脚本固定 `cd /workspace`，本地宿主机直接运行会失败；需在 compose 容器环境验证。
