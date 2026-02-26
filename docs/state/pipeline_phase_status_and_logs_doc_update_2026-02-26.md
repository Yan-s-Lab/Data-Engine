# Pipeline Phase 状态核对与日志文档补充（2026-02-26）

## 背景
- 目标：回答“docker pipeline 当前到哪个 phase”并补充日志查看文档。

## 运行状态核对（本次检查）
- 容器状态：`dataengine-pipeline` 处于 `Restarting`。
- 最近一次有效串行计划摘要：`artifacts/logs/serial_plan_summary_20260225_201731.json`。
  - `dataloader/dataloader_norm`：成功
  - `generation/prompt_only`：成功
  - `generation/prompt_canny`：失败（`return_code=1`）
- 因此：最近一次有效执行停在 **generation phase**，尚未进入 filter phase。
- 当前重启原因：容器日志显示 `FileNotFoundError: config not found: deploy/pipeline/pipeline_serial_plan.example.yaml`。

## 本次文档更新
- 更新 `docs/README_PIPELINE_ZH.md`：
  - 串行计划示例路径改为现有文件 `deploy/pipeline/pipeline_serial_plan.example-yk003.yaml`。
  - 在 Docker 小节补充：
    - 宿主机文件日志查看方式（`artifacts/logs/*`）
    - 如何判断“当前跑到哪个 phase / 卡在哪个 phase”（`ps` + `serial_plan_summary` + 任务日志）
