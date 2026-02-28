# Generation：prompt+canny 测试配置字段对齐（2026-02-28）

## Scope
- 仅对齐 `test/test-generation/config/generation/deltoid_muscle_seg_prompt_canny.yaml` 的字段表达与当前 generation 实现语义。
- 不调整生成算法与 workflow 节点逻辑。

## Changes
- `test/test-generation/config/generation/deltoid_muscle_seg_prompt_canny.yaml`
  - `generate.manifest.profile` 显式设置为 `core`（与当前默认产物形态一致）。
  - 显式补充 `generate.comfyui.persist_outputs: false`。
  - 显式补充 `generate.comfyui.output_dir: data/comfyui/output`。

## Notes
- 本次不引入 `max_outputs_per_job`（已废弃）。
- 本次不新增 `batch_size` 注入：当前 `flux_canny_model_example.json` 未使用 `batch_size` 节点输入。
