# Pipeline 托管容器化改造（2026-02-25）

## Scope
- 解决当前前台 shell 运行 pipeline 在 SSH 断开/锁屏时易中断的问题。
- 提供机器重启后的自动拉起能力。
- 在现有实现上增加最小可用的续跑与单实例保障。

## Changes
- 新增托管 runner：`pipelines/run_managed_pipeline.py`
  - 单实例锁：`managed.lock`
  - PID 文件：`managed.pid`
  - 信号处理：`SIGTERM/SIGINT` 优雅退出，`SIGHUP` 忽略
  - 断点续跑：`pipeline.resume_from_artifacts` 默认 `true`
  - 运行摘要：`pipeline/summary.json`
- 新增容器部署文件：
  - `deploy/pipeline/Dockerfile`
  - `deploy/pipeline/pipeline_entrypoint.sh`
  - `deploy/pipeline/docker-compose.pipeline.yml`
  - `deploy/pipeline/.env.example`
- 新增 systemd 部署文件：
  - `deploy/systemd/dataengine-pipeline.service`
  - `deploy/systemd/install_pipeline_service.sh`
- 新增测试：`test/test_managed_pipeline_smoke.py`
  - 验证首次执行与二次续跑跳过逻辑。
- 更新文档：`docs/README_PIPELINE_ZH.md`

## Validation
```bash
python -m unittest discover -s test -p 'test_managed_pipeline_smoke.py' -v
```

## Notes
- 容器层通过 `restart: always` 保证容器退出后自动重启。
- 主机重启场景通过 `systemd` 服务自动启动 compose，恢复 pipeline。
