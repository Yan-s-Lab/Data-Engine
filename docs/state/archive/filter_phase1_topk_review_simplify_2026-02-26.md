# Filter Phase1 简化为 Top-K + Expert 审核（2026-02-26）

## Scope
- 仅针对 filter phase1 评估与分桶可解释性做简化。
- 不新增其它评估功能；仅保留 phase1 两类核心信号。

## Changes
- `filter/run_filter.py`
  - 新增 `policy.ranking_review` 后处理：
    - 对目标源（默认 synthetic）按 `rank_metric` 排序。
    - `keep_top_k` 或 `keep_top_ratio` 进入 `accept`。
    - 其余样本在 `review_rest=true` 时进入 `uncertain`（Expert 审核池），不直接 reject。
  - 新增 compare log 终态标注：
    - `decision_final`
    - `decision_basis_final`
    - `rank_position`
    - `rank_value`

- `test/test-filters/configs/filter_compose.yaml`
  - stage 精简：
    - 保留 `semantic_anchor`、`prompt_score`
    - 关闭 `prompt_margin`、`anchor_ood`、`quality`、`consistency`、`multicrop`、`dedup`
  - policy 精简：
    - `decision: weighted`
    - `weighted.final_score` 仅保留 `s_phase1_semantic: 1.0`
  - 新增：
    - `policy.ranking_review.enabled: true`
    - `policy.ranking_review.keep_top_k: 6`
    - `policy.ranking_review.review_rest: true`

- `test/test_filter_phase1_semantic.py`
  - 新增 `test_topk_review_selection` 覆盖 Top-K + review 分桶逻辑。

## Validation
```bash
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
```

关键结果：
- `total=14`
- `accept=8`
- `uncertain=6`
- `reject=0`
- synthetic（12 条）中：`top-6 accept`，其余 `6 条 uncertain` 进入 Expert 审核池。
