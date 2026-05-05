# Generation manifest 分层（core profile，2026-02-27）

## Scope
- 在不破坏现有主流程的前提下，降低 generation 产物的默认追踪复杂度。
- 保留 core functions，复杂字段归为可选 capabilities。

## Implementation
- 更新 `synth/run_generate.py`：
  - 新增 `generate.manifest.*` 配置：
    - `profile: compat|core`（默认 `core`）
    - `write_trace_artifacts: true|false`（默认 `false`）
  - 新增 trace 清单构建逻辑（核心追踪字段）：
    - `sample_id`, `source`, `image_path`
    - `prompt_text`, `seed`
    - `guide_image`, `guide_type`
    - `width`, `height`
    - `config_ref`
    - `anchor_real_sample_id`
  - 输出策略：
    - `profile=core`：`synth_manifest/mixed_manifest` 直接写核心字段（默认）。
    - `profile=compat`：按需回退为历史全字段。
    - 仅在 `write_trace_artifacts=true` 时额外写 trace 清单。
  - `report.json` 增加 `manifest_profile` 与可选 trace 路径记录。

## Tests
- 新增 `test/test_generate_manifest_profile.py`：
  - 覆盖 `manifest.profile` 默认值与非法值校验。
  - 覆盖 trace 行核心字段生成。

## Compatibility
- 默认改为最简输出（`profile=core`，不额外 trace/debug 文件）。
- 如需历史字段，显式设置 `generate.manifest.profile=compat`。
