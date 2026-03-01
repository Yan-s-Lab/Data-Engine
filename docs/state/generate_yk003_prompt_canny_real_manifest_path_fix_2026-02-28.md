# Generation：yk003 prompt_canny real_manifest 路径修复（2026-02-28）

## Issue
- `configs/task_body_generation/generation/body_pose_prompt_canny.yaml` 的 `generate.real_manifest` 指向
  `artifacts/runs/yk003/body_pose/dataloader/real_manifest.jsonl`。
- 实际 dataloader 产物位于带 `run_id` 的目录：
  `artifacts/runs/yk003/body_pose/yk003_body_datanorm/dataloader/real_manifest.jsonl`。
- 导致 generation 启动即报错：`FileNotFoundError: missing real manifest`。

## Fix
- 更新 `configs/task_body_generation/generation/body_pose_prompt_canny.yaml`：
  - `generate.real_manifest` -> `artifacts/runs/yk003/body_pose/yk003_body_datanorm/dataloader/real_manifest.jsonl`

## Validation
- 本地文件存在性检查通过：`test -f artifacts/runs/yk003/body_pose/yk003_body_datanorm/dataloader/real_manifest.jsonl`。
- 修复后不再触发该路径缺失错误。
