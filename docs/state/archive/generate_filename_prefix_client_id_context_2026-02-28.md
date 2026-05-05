# Generation：filename_prefix.template 支持 client_id 上下文（2026-02-28）

## Scope
- 仅补齐 generation 阶段 `filename_prefix.template` 的 `client_id` 变量注入。
- 不改生成数量逻辑，不改 manifest schema。

## Changes
- `synth/comfyui_workflow.py`
  - `set_workflow_filename_prefix` 新增参数 `client_id`。
  - 模板 context 新增键：`client_id`（取自 `generate.comfyui.client_id`）。
- `synth/run_generate.py`
  - 调用 `set_workflow_filename_prefix` 时传入已解析的 `client_id`。
- `docs/kernels/control_generation.md`
  - 文件名前缀变量说明新增 `client_id`/`run_id`。

## Notes
- 现在模板 `"{client_id}__{run_id}__{sample_index}"` 会按配置中的 `generate.comfyui.client_id` 正常替换。
