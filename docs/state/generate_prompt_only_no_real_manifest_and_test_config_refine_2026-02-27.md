# Generation refine：prompt-only 去 real_manifest 依赖 + test 配置清晰化（2026-02-27）

## Scope
- 仅收敛 generation 的输入边界与 test 配置可读性。
- 不改 filter/training，不引入新架构层。

## Changes
- `synth/run_generate.py`
  - 新增规则：`backend=comfyui` 且 `manifest.guide_type=prompt` 时，允许 `real_manifest` 缺失或为空。
  - 纯 prompt-only 且无 anchor 配置时，使用虚拟单锚执行循环，生成数量由：
    - `max_synth_samples`（优先）
    - 或 `synth_per_real`（兜底）
  - 若配置了 `anchor_image/anchor_images`，仍强制要求非空 `real_manifest`。
- `test/test_generate_manifest_profile.py`
  - 增加 `_allow_prompt_only_without_real_manifest` 行为测试。
- test-generation 配置重写（Input / Implement / Output）：
  - `test/test-generation/config/generation/deltoid_muscle_seg_prompt.yaml`
    - 去掉 `real_manifest`，保留 prompt-only 最小必需配置。
    - 明确注释哪些字段会覆盖 ComfyUI API graph 的 `node.inputs`。
    - `max_outputs_per_job` 调整为 `2`，与 workflow `batch_size=2` 对齐。
  - `test/test-generation/config/generation/deltoid_muscle_seg_prompt_canny.yaml`
    - 保留 `real_manifest`（image-guided 必需）。
    - 明确 anchor 注入路径与 API graph 覆盖字段。
- `docs/kernels/control_generation.md`
  - 补充 prompt-only 可省略 `real_manifest` 的边界。
  - 补充 `max_outputs_per_job` 与 workflow `batch_size` 的关系。

## Validation
- `python -m py_compile synth/run_generate.py`
- `python -m unittest discover -s test -p 'test_generate_manifest_profile.py' -v`
