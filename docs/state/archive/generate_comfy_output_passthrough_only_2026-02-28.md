# Generation：ComfyUI 输出改为直连挂载目录（2026-02-28）

## Scope
- 仅调整 generation 阶段 ComfyUI 输出文件获取策略。
- 不改 prompt/anchor 注入逻辑，不改 filter 逻辑。

## Changes
- `synth/comfyui_client.py`
  - `download_history_outputs` 不再调用 `/view` 下载图片。
  - 仅接收 `type=output`（SaveImage）结果，忽略 `PreviewImage` 等 `type=temp` 中间图。
  - 仅引用 `generate.comfyui.output_dir` 下已存在文件；文件不存在则跳过该条输出。
- `synth/run_generate.py`
  - 移除 `persist_outputs` 调用链路。
  - `generate_with_comfyui` 去掉未使用的 `img_dir` 参数。
- 测试配置
  - `test/test-generation/config/generation/deltoid_muscle_seg_prompt.yaml`
  - `test/test-generation/config/generation/deltoid_muscle_seg_prompt_canny.yaml`
  - 删除 `persist_outputs`，保留 `output_dir`。
- 文档
  - `docs/kernels/control_generation.md`：更新输出策略说明。

## Notes
- 该改动解决了 `generate/images/ComfyUI_temp_*` 被写入并污染 manifest 的问题。
