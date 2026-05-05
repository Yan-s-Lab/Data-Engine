# Filter Phase1 prompt 改为 raw cosine + real 分位数阈值（2026-02-26）

## Scope
- 对 phase1 prompt 指标口径做可解释性修正，并增加 real-anchor 分位数阈值标定。
- 不改动 anchor 相似度计算与 Top-K 审核主策略。

## Changes
- `filter/run_filter.py`
  - 新增 `phase1_semantic.prompt_metric: raw_cosine`
    - 通过 cosine 得分反算 raw cosine：`raw = 2*mapped - 1`，范围 `[-1,1]`
  - `build_phase1_semantic_scores` 按 `prompt_metric` 选择 `s_prompt` 的值域处理：
    - `raw_cosine` -> `[-1,1]`
    - `margin` -> 原值
    - 其余保持 `[0,1]`
  - `ranking_review` 新增：
    - `guided_min_prompt_from_real_quantile`（`q05/q10/q25/q50/q75/q90/q95`）
    - 开启后，用 real 样本 `s_prompt` 分位数覆盖 `guided_min_prompt`
  - `report.json.phase1_semantic.prompt_real_quantiles` 回填 real 标定统计。

- `test/test-filters/configs/filter_compose.yaml`
  - `clip.prompt_score_mode: cosine`
  - `phase1_semantic.prompt_metric: raw_cosine`
  - `policy.ranking_review.guided_min_prompt_from_real_quantile: q10`

- `docs/kernels/filter_phase1.md`
  - 同步 `raw_cosine` 指标与 quantile 阈值字段说明。

## Validation
```bash
python -m py_compile filter/run_filter.py
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
```

关键结果：
- `report.json.phase1_semantic.prompt_metric = raw_cosine`
- `report.json.phase1_semantic.prompt_real_quantiles.q10 = 0.029709`
- `ranking_review.guided_min_prompt = 0.029709`（来自 q10 标定）
- 关注样本 `yk-001_arm_deltoid_muscle_seg_0006_canny_0003`：
  - `s_prompt = 0.027155`
  - `decision = uncertain`
