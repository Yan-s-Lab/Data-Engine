# Filter Phase1 启用 prompt margin_norm 指标（2026-02-26）

## Scope
- 仅调整 phase1 中 `s_prompt` 的来源口径，解决 `cosine` 映射后分数集中在 `0.5` 附近的问题。
- 不改动 Top-K 审核策略与 anchor 计算逻辑。

## Changes
- `filter/run_filter.py`
  - phase1 新增 `phase1_semantic.prompt_metric`：
    - `score`（默认）：沿用原 `compute_prompt_scores`
    - `margin_norm`：使用 `compute_prompt_margin_scores` 的 `s_prompt_margin_norm` 作为 `s_prompt`
  - `report.json.phase1_semantic.prompt_metric` 回填当前口径。

- `test/test-filters/configs/filter_compose.yaml`
  - `filter.clip.prompt_score_mode: siglip_sigmoid`
  - `filter.phase1_semantic.prompt_metric: margin_norm`

- `docs/kernels/filter_phase1.md`
  - 补充 `s_prompt` 的两种口径说明（`score` / `margin_norm`）。

## Validation
```bash
python -m py_compile filter/run_filter.py
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
```

关键结果：
- 对焦样本 `yk-001_arm_deltoid_muscle_seg_0006_canny_0003`：
  - `s_prompt = 0.056778`（低）
  - `decision = uncertain`
