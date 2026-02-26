# Filter Phase1 收敛为极简 v1（2026-02-26）

## Scope
- 仅针对 phase1 浅过滤逻辑收敛。
- 保留 SigLIP2 语义过滤核心：`prompt` 与 `image anchor`。
- 去除 phase1 路由融合、资格旁路规则与历史冗余输出字段。

## Changes
- `filter/run_filter.py`
  - `build_phase1_semantic_scores` 收敛为 v1：
    - 输出 `s_anchor`、`s_prompt`、`s_final`。
    - guided：`s_final = guided_w_anchor * s_anchor + guided_w_prompt * s_prompt`。
    - prompt-only：`w_anchor=0, w_prompt=1`。
  - `_apply_topk_review_selection` 收敛为单一策略：
    - guided 最小资格：`s_anchor>=guided_min_anchor && s_prompt>guided_min_prompt`。
    - 资格内按 `s_final` 排序取 Top-K accept。
    - 其余默认全部 uncertain。
    - `hard_reject=false` 时 reject=0。
  - compose 模式输出字段瘦身，移除 phase1 compare log 与 gate 相关旁路输出。

- `test/test-filters/configs/filter_compose.yaml`
  - phase1 配置简化为：
    - `guided_w_anchor` / `guided_w_prompt`
    - `ranking_review.rank_metric=s_final`
    - `guided_min_anchor` / `guided_min_prompt`
    - `hard_reject=false`
  - 移除 `guided_fusion` 与 `accept_eligibility` 规则。

- `test/test_filter_phase1_semantic.py`
  - 改为覆盖 v1 核心行为：
    - `s_anchor/s_prompt/s_final` 计算正确。
    - guided 最小资格 + Top-K 分桶。
    - 默认无 reject，`hard_reject=true` 时才 reject。

- `docs/kernels/filter_phase1.md`
  - 更新为 phase1 v1 极简说明（双分数、统一总分、单一分桶）。

## Validation
```bash
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
```

关键结果：
- 单测：`Ran 4 tests ... OK`
- 运行结果：
  - `total=14`
  - `accept=8`
  - `uncertain=6`
  - `reject=0`
