# Generation：移除 manifest.profile 抽象开关（2026-02-28）

## Scope
- 收敛 generation manifest 配置，删除 `profile/compat` 双轨抽象。
- 保留单一 `synth_manifest` 输出语义（当前 core 字段）。

## Changes
- `synth/generate_manifest.py`
  - 删除 `generate.manifest.profile` 解析与校验。
  - 删除 `compat` 分支，`synth_manifest.jsonl` 固定写核心追踪字段。
- `synth/run_generate.py`
  - `report.json` 删除 `manifest_profile` 字段。
- `test/test_generate_manifest_profile.py`
  - 删除 `profile` 默认值与非法值校验断言。
- `test/test-generation/config/generation/deltoid_muscle_seg_prompt_canny.yaml`
  - 删除 `manifest.profile` 配置项。
- `docs/kernels/control_generation.md`
  - 删除 `manifest.profile` 文档说明，改为单一路径描述。

## Validation
- `python -m py_compile synth/run_generate.py synth/generate_manifest.py`
- `python -m unittest discover -s test -p 'test_generate_manifest_profile.py' -v`
