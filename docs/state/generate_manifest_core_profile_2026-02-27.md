# Generation manifest 分层（core profile，2026-02-27）

## Scope
- 在不破坏现有主流程的前提下，降低 generation 产物的默认追踪复杂度。
- 保留 core functions，复杂字段归为可选 capabilities。

## Implementation
- 更新 `synth/run_generate.py`：
  - 新增 `generate.manifest.*` 配置：
    - `profile: compat|core`（默认 `compat`）
    - `write_trace_artifacts: true|false`（默认 `true`）
    - `write_compat_when_core: true|false`（默认 `true`）
  - 新增 trace 清单构建逻辑（核心追踪字段）：
    - `sample_id`, `source`, `image_path`
    - `prompt_text`, `seed`
    - `guide_image`, `guide_type`
    - `width`, `height`
    - `config_ref`
    - `anchor_real_sample_id`
  - 输出策略：
    - `profile=compat`：`synth_manifest/mixed_manifest` 维持全字段；额外写 `synth_trace_manifest/mixed_trace_manifest`。
    - `profile=core`：`synth_manifest/mixed_manifest` 改为核心字段；可选额外写 `synth_debug_manifest/mixed_debug_manifest`。
  - `report.json` 增加 `manifest_profile` 与 trace/compat 路径记录。

## Tests
- 新增 `test/test_generate_manifest_profile.py`：
  - 覆盖 `manifest.profile` 默认值与非法值校验。
  - 覆盖 trace 行核心字段生成。

## Compatibility
- 默认配置不变（`profile=compat`），不会影响现有 filter/pipeline。
- 需要简化产物时，显式设置 `generate.manifest.profile=core`。
