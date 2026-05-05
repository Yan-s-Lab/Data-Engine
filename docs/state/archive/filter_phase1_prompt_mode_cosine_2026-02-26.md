# Filter Phase1 prompt 打分模式切换为 cosine（2026-02-26）

## Scope
- 仅调整 phase1 prompt 指标的打分口径与 guided 最低 prompt 资格阈值。
- 不修改其它 filter 算法或流程。

## Changes
- `test/test-filters/configs/filter_compose.yaml`
  - `filter.clip.prompt_score_mode`: `siglip_sigmoid -> cosine`
  - `filter.policy.ranking_review.guided_min_prompt`: `0.0 -> -1.0`

## Validation
```bash
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
```

关键结果：
- `report.json.prompt_score_mode = cosine`
- synthetic `s_prompt` 不再接近 0（约 `0.506 ~ 0.535`）
