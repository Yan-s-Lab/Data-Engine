# Generation core manifest 固定输出 guide_image_id（2026-02-27）

## Scope
- 仅修正 generation core manifest schema 稳定性。
- 不调整 filter/训练逻辑，不改任务路由。

## Changes
- `synth/run_generate.py`
  - `build_synth_manifest_rows` 固定输出 `guide_image_id` 字段。
  - 取值优先级：`guide_image_id` -> `anchor_real_sample_id` -> `""`。
  - prompt-only 模式下该字段为空字符串，但字段存在。
- `test/test_generate_manifest_profile.py`
  - 补充断言：guided 行必须带 `guide_image_id`。
  - 补充断言：prompt-only 行必须存在 `guide_image_id` 且值为空。
- `docs/kernels/control_generation.md`
  - core 字段说明补充 `guide_image_id`（prompt-only 可为空）。

## Validation
- `python -m py_compile synth/run_generate.py`
- `python -m unittest discover -s test -p 'test_generate_manifest_profile.py' -v`
