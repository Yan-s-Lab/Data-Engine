# Pipeline Docker 编排 Demo 文档补充（2026-02-25）

## Scope
- 为主索引文档补充容器编排可执行命令示例。
- 覆盖启动、终止、重启、状态与日志查看。

## Changes
- 更新 `docs/README_PIPELINE_ZH.md`：
  - 新增「Docker 容器编排 Demo（启动 / 终止 / 重启）」章节。
  - 增加 `.env` 三种运行模式说明：
    - `PIPELINE_CONFIG`
    - `PIPELINE_CONFIGS/PIPELINE_CONFIG_LIST_FILE`
    - `PIPELINE_SERIAL_PLAN`
  - 增加 `docker compose` 命令示例：
    - `up --build`（前台/后台）
    - `ps`
    - `logs -f --tail 200`
    - `down`
    - `restart`
    - `up --force-recreate`
  - 增加可选 `systemctl start/stop/restart` 命令示例。
