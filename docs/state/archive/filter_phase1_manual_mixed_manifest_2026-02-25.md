# Filter Phase1 手工 mixed_manifest 验证（2026-02-25）

## Scope
- 仅调整 `test/test-filters` 的 phase1 验证输入与配置。
- 不改动 filter 算法实现。

## Changes
- 更新 `test/test-filters/generate/mixed_manifest.jsonl`：
  - real: 2 条
  - synthetic: 12 条
  - guided synthetic（带 `anchor_real_sample_id`）: 7 条
  - prompt-only synthetic: 5 条
- 更新 `test/test-filters/configs/filter_compose.yaml`：
  - `filter.input_manifest` 指向 `test/test-filters/generate/mixed_manifest.jsonl`
  - `manifest_builder.force_rebuild: false`，避免覆盖手工 manifest

## Validation
```bash
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
```

关键结果（`test/test-filters/runs/testfilter_compose/filter/report.json`）：
- `semantic_anchor.anchor_count = 2`
- `phase1_semantic.guided_synth_count = 7`
- `phase1_semantic.prompt_only_synth_count = 5`
- `phase1_semantic.source_counter.semantic_pair = 7`
- `phase1_semantic.source_counter.prompt_score = 5`

说明 phase1 路由已按目标命中：guided -> `semantic_pair`，prompt-only -> `prompt_score`。
