# Filter phase1 运行：clean synth mixed manifest（2026-02-26）

## Scope
- 针对 `clean_synth_manifest_2026-02-26.jsonl` 中 `s_anchor=0` 问题，补入 real anchor 行后重跑 phase1。
- 不改 filter 算法，仅修正输入 manifest 形态（synthetic + real anchors）。

## Input Preparation
- 原清单：`artifacts/user_runs/clean_synth_manifest_2026-02-26.jsonl`（仅 synthetic）
- 补锚后清单：`artifacts/user_runs/clean_synth_mixed_manifest_2026-02-26.jsonl`
  - synthetic: 1052
  - 新增 real anchors: 131
  - total: 1183

## Config
- 新增配置：
  - `configs/examples/filter_phase1_clean_synth_mixed_2026-02-26.yaml`
- 输入：
  - `filter.input_manifest: artifacts/user_runs/clean_synth_mixed_manifest_2026-02-26.jsonl`

## Execution
```bash
conda run -n dataengine python filter/run_filter.py \
  --config configs/examples/filter_phase1_clean_synth_mixed_2026-02-26.yaml
```

## Result Summary
- `total=1183`
- `accept=404`
- `uncertain=779`
- `reject=0`
- `accept_ratio=0.3415`

配对恢复情况：
- `phase1_semantic.guided_synth_count=476`
- `phase1_semantic.guided_anchor_hit_count=476`
- `phase1_semantic.paired.pair_hit_count=476`
- `phase1_semantic.paired.pair_miss_count=707`

`filter_scores.jsonl` 统计：
- synthetic 总数 `1052`
- `s_anchor>0` 数量 `476`
- `s_anchor=0` 数量 `576`（对应 prompt-only synthetic）

## Output Artifacts
- `artifacts/user_runs/clean_synth_mixed_filter_phase1_20260226/filter/filter_scores.jsonl`
- `artifacts/user_runs/clean_synth_mixed_filter_phase1_20260226/filter/splits/accept.jsonl`
- `artifacts/user_runs/clean_synth_mixed_filter_phase1_20260226/filter/splits/reject.jsonl`
- `artifacts/user_runs/clean_synth_mixed_filter_phase1_20260226/filter/splits/uncertain.jsonl`
- `artifacts/user_runs/clean_synth_mixed_filter_phase1_20260226/filter/report.json`
