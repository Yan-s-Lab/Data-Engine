# Filter Phase1 路由化 Gate（2026-02-25）

## Scope
- 仅调整 filter phase1 的 gate 生效逻辑与测试配置。
- 目标：避免 prompt-only 样本被 real semantic gate 误杀。

## Changes
- `filter/run_filter.py`
  - 新增 gate 条件匹配：
    - `sources` / `sources_exclude`
    - `phase1_sources` / `phase1_sources_exclude`
  - 当 gate 条件不匹配时，记录 skip，不参与该样本 gate 判定。
  - 若某样本没有任何 gate 生效，回退到 weighted 阈值判定（不默认 accept）。

- `test/test-filters/configs/filter_compose.yaml`
  - `s_phase1_semantic` gate 仅作用于 `phase1_source in [semantic_pair, semantic_anchor]`。
  - 新增 `prompt-only` 路由 gate：
    - `metric: s_prompt_margin_norm`
    - `threshold: 0.25`
    - `phase1_sources: [prompt_score]`

- `test/test_filter_phase1_semantic.py`
  - 新增 gate 条件单测，覆盖 `phase1_sources` 匹配行为。

## Validation
```bash
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
```

关键结果（`test/test-filters/runs/testfilter_compose/filter/report.json`）：
- 旧：`accept=7, reject=7, accept_ratio=0.5`
- 新：`accept=11, reject=3, accept_ratio=0.7857`

样本 `prompt_only_59_20260271_00002_`：
- 旧：`reject`（semantic gate fail）
- 新：`accept`（semantic gate skip；prompt gate pass）
