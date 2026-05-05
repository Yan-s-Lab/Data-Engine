# Generation Prompt-only 清单收敛（2026-02-27）

## Scope
- 仅调整 `synth/run_generate.py` 的 ComfyUI 输出落地策略与 core manifest 字段。
- 不改 filter/training 逻辑。

## Changes
- ComfyUI 输出路径策略：
  - 新增 `generate.comfyui.persist_outputs`（默认 `false`）。
  - `persist_outputs=false` 时，`image_path` 直接指向 `generate.comfyui.output_dir`（默认 `data/comfyui/output`），不再强制写 `run_dir/generate/images`。
  - 当 `output_dir` 下找不到目标文件时自动回退下载到 `run_dir/generate/images`。
- `sample_id` 规则：
  - 改为 ComfyUI 输出文件 stem（例如 `prompt_only_0_20260225_00005_`），不再使用 `synth_00000` 本地编号。
- core manifest 字段调整：
  - 移除冗余 `effective_prompt_text`（保留 `prompt_text`）。
  - `guide_type` 统一为 `prompt | image_guided`（real 行为空字符串）。
  - `guide_image` 仅来自实际注入的 anchor 输入。
  - `anchor_real_sample_id` 改为可选字段（有值才写）。
  - 新增 `synthetic_image_ids`（数组，表示同一 prompt job 的输出 ids）。
- 示例配置：
  - 更新 `configs/examples/comfyui_generate_from_norm_yk003_prompt_only_managed.yaml`，显式给出 `persist_outputs: false` 与 `output_dir: data/comfyui/output`。

## Validation
- `python -m unittest discover -s test -p 'test_generate_manifest_profile.py' -v`
