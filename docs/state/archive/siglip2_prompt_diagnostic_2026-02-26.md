# SigLIP2 Prompt 指标追查（2026-02-26）

## Scope
- 追查 filter phase1 中 prompt 指标对非目标样本（示例：dog + latent）识别不明显的问题。
- 不改动主流程算法；仅新增诊断脚本并产出诊断报告。

## Changes
- 新增脚本：
  - `test/test-filters/scripts/diagnose_siglip2_prompt_scores.py`
- 脚本输出：
  - `test/test-filters/runs/testfilter_compose/filter/siglip2_prompt_diagnostic.json`

## How to Run
```bash
python test/test-filters/scripts/diagnose_siglip2_prompt_scores.py \
  --config test/test-filters/configs/filter_compose.yaml \
  --focus-sample-id yk-001_arm_deltoid_muscle_seg_0006_canny_0003
```

## Key Findings
- 现有 `cosine_mapped_01`（`(cos+1)/2`）会把中性样本聚集在 `0.5` 附近，导致“坏图看起来也像 0.5x”。
- 对焦样本 `yk-001_arm_deltoid_muscle_seg_0006_canny_0003`：
  - `cosine_mapped_01 = 0.5136`（表面看似中等）
  - `cosine_raw_neg1_pos1 = 0.0272`（实际接近中性）
  - `siglip_logit_margin = -2.8102`（正向提示词明显弱于负向提示词）
  - `siglip_margin_norm = 0.0568`（低）
- 结论：问题主要在指标口径可读性与策略使用，而非“模型完全无信号”。
