# Generation: 移除 max_outputs_per_job，改为 graph batch_size 真注入（2026-02-28）

## Scope
- 仅收敛 generate 阶段 ComfyUI 单任务产图数量控制参数。
- 不改 filter/training 阶段。

## Changes
- `synth/comfyui_workflow.py`
  - 新增 `set_workflow_batch_size`：支持通过
    `generate.comfyui.batch_size.{node_id,input_key,value}` 注入 workflow 节点输入。
- `synth/run_generate.py`
  - 接入 `generate.comfyui.batch_size` 解析与校验。
  - 每次提交前将 batch_size 注入到 workflow API graph。
  - 删除 `max_outputs_per_job` 的解析与调用链路。
- `synth/comfyui_client.py`
  - `download_history_outputs` 不再按 `max_outputs_per_job` 截断。
- 配置更新
  - `test/test-generation/config/generation/deltoid_muscle_seg_prompt.yaml`
    - 删除 `max_outputs_per_job`。
    - 新增 `batch_size` 注入示例（node `27`, `batch_size=4`）。
  - 清理其它示例/测试配置中的 `max_outputs_per_job`。
- 文档更新
  - `docs/kernels/control_generation.md`：将控制语义从 `max_outputs_per_job` 更新为 `batch_size` graph 注入。

## Notes
- 真实单个 ComfyUI running 产图数由 workflow 节点的 `batch_size` 决定。
- 总体生成上限仍由 `max_synth_samples` 控制。

## Validation
- `python -m py_compile synth/run_generate.py synth/comfyui_client.py synth/comfyui_workflow.py`
