# Filter phase1 运行：clean synth manifest（2026-02-26）

## Scope
- 基于 `artifacts/user_runs/clean_synth_manifest_2026-02-26.jsonl` 重新执行 Filter phase1。
- 该清单只包含 synthetic，且 synthetic 源固定为 `data/comfyui/output`。

## Config
- 新增配置：
  - `configs/examples/filter_phase1_clean_synth_2026-02-26.yaml`
- 关键输入：
  - `filter.input_manifest: artifacts/user_runs/clean_synth_manifest_2026-02-26.jsonl`

## Execution
```bash
conda run -n dataengine python filter/run_filter.py \
  --config configs/examples/filter_phase1_clean_synth_2026-02-26.yaml
```

## Result Summary
- `total=1052`
- `accept=173`
- `uncertain=879`
- `reject=0`
- `accept_ratio=0.1644`

phase1 关键状态：
- `guided_synth_count=476`
- `prompt_only_synth_count=576`
- `guided_anchor_hit_count=0`
- `paired.pair_hit_count=0`
- `paired.pair_miss_count=1052`

ranking_review：
- `candidate_total=1052`
- `eligible_total=576`
- `keep_count=173`
- `ineligible_count=476`

## Output Artifacts
- `artifacts/user_runs/clean_synth_filter_phase1_20260226/filter/filter_scores.jsonl`
- `artifacts/user_runs/clean_synth_filter_phase1_20260226/filter/splits/accept.jsonl`
- `artifacts/user_runs/clean_synth_filter_phase1_20260226/filter/splits/reject.jsonl`
- `artifacts/user_runs/clean_synth_filter_phase1_20260226/filter/splits/uncertain.jsonl`
- `artifacts/user_runs/clean_synth_filter_phase1_20260226/filter/report.json`
