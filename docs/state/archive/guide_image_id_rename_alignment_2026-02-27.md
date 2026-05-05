# guide_image_id 字段对齐（2026-02-27）

## Scope
- 对齐 generation/filter 侧的 guided anchor 样本 id 命名。
- 将默认字段从 `anchor_real_sample_id` 迁移为 `guide_image_id`。
- 保留旧字段读取兼容，避免历史 manifest 直接失效。

## Changes
- `synth/run_generate.py`
  - guided 关联 id 写入 `guide_image_id`（替代 `anchor_real_sample_id`）。
- `filter/run_filter.py`
  - guided marker 默认优先 `guide_image_id`。
  - 读取 manifest 时做兼容映射：若无 `guide_image_id`，自动回填 `anchor_real_sample_id`。
- `filter/filter_stages/clip_semantic_anchor.py`
  - anchor sid 默认字段优先级改为 `guide_image_id` -> `anchor_real_sample_id`。
- `filter/manifest_builder.py`
  - synthetic anchor 默认字段改为 `guide_image_id`。
- `synth/build_clean_synth_manifest.py`
  - clean manifest 输出字段改为 `guide_image_id`，并兼容读取旧字段。
- configs/tests/docs
  - phase1 配置和测试示例中的默认字段改为 `guide_image_id`。

## Validation
- `python -m py_compile filter/run_filter.py filter/filter_stages/clip_semantic_anchor.py filter/manifest_builder.py synth/build_clean_synth_manifest.py`
- `python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v`
- `python -m unittest discover -s test -p 'test_filter_input_manifest_resolution.py' -v`
