# Generation：filename_prefix anchor 变量切换为 norm-only（2026-02-28）

## Scope
- 仅收敛 generation 阶段 `filename_prefix.template` 的 anchor 名称变量来源。
- 不改 prompt/anchor 注入流程，不改 synth manifest schema。

## Changes
- `synth/comfyui_workflow.py`
  - `_inject_anchor_name_context` 不再读取 `original_image_path`。
  - `anchor_image_stem` / `anchor_image_name` 统一来自 `real_manifest.image_path`（norm 路径）。
  - `anchor_image_stem_norm` / `anchor_image_name_norm` 保持与上述字段一致。
  - 移除历史兼容上下文字段：`anchor_image_stem_raw` / `anchor_image_name_raw`。
- `docs/kernels/control_generation.md`
  - 补充 `filename_prefix.template` 变量语义：`anchor_image_*` 仅基于 norm 路径。

## Notes
- 对于模板 `"{run_id}__{anchor_image_stem}"`，输出后缀将使用 norm 后文件名 stem（例如 `yk003_deltoid_muscle_seg_0001`），不再使用原始图片 stem（例如 `yk-003_arm_deltoid_muscle_0013`）。
