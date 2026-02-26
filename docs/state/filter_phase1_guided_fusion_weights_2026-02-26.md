# Filter Phase1 Guided 双指标融合（2026-02-26）

## Scope
- 为 guided synthetic 增加可配置的双指标融合，不改变 prompt-only 路由逻辑。

## Changes
- `filter/run_filter.py`
  - `phase1_semantic.guided_fusion` 新增融合配置：
    - `enabled`
    - `method`: `weighted_sum | geometric_mean | harmonic_mean`
    - `pair_weight`
    - `prompt_weight`
  - 当 guided 且 pair 命中时：
    - 旧：`s_phase1_semantic = s_semantic_pair`
    - 新（启用融合）：`s_phase1_semantic = fuse(s_semantic_pair, s_prompt)`
    - `s_phase1_semantic_source = semantic_pair_fused`
  - `phase1_sources` gate 匹配增强：`semantic_pair_fused` 可匹配 `semantic_pair` 条件。
  - compare log 对融合样本备注为 `guided synthetic fused anchor+prompt score`。

- `test/test-filters/configs/filter_compose.yaml`
  - 在 `phase1_semantic` 下启用融合示例：
    - `guided_fusion.enabled: true`
    - `guided_fusion.method: weighted_sum`
    - `pair_weight: 0.8`
    - `prompt_weight: 0.2`

- `test/test_filter_phase1_semantic.py`
  - 新增融合单测 `test_guided_fusion_weighted_sum`。
  - gate 条件单测增加 `semantic_pair_fused` 兼容验证。

## Validation
```bash
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
```

关键结果：
- `report.json.phase1_semantic.guided_fusion` 正确回填融合配置。
- guided 样本 `s_phase1_semantic_source = semantic_pair_fused`。
