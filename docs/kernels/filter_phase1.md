# Kernel: Filter (Phase1)

## 1. 作用

对 generation 输出进行 phase1 语义筛选，产出 `accept/reject/uncertain` 三分结果。

入口脚本：
- `filter/run_filter.py`
- 当前仅支持：`filter.mode=compose`（phase1 v1）

## 2. Phase 输入输出关系

- 输入：
  - 推荐：`<run_dir>/generate/synth_manifest.jsonl`
  - 或显式 `filter.input_manifest`
- 输出：
  - `<run_dir>/filter/filter_scores.jsonl`
  - `<run_dir>/filter/splits/accept.jsonl`
  - `<run_dir>/filter/splits/reject.jsonl`
  - `<run_dir>/filter/splits/uncertain.jsonl`
  - `<run_dir>/filter/report.json`
    - 包含 `input_total`（补锚前输入数）与 `anchor_real_injection`（补锚来源/数量）
- 下游关系（目标态）：
  - `accept/uncertain` 进入 annotation / HITL / training

## 3. 推荐配置

- `test/test-filters/configs/filter_compose.yaml`

## 4. Phase1 v1（极简）

1. 输入清单优先级
- `filter.input_manifests`（显式多输入，按顺序合并）
- `filter.input_manifest`（显式）
- `<run_dir>/generate/synth_manifest.jsonl`（默认自动）
- `<run_dir>/generate/mixed_manifest.jsonl`（历史兼容回退）
- `manifest_builder`（启用时）
- stub manifest（兜底）

1.1 多输入合并去重（`filter.input_manifests`）
- 默认按 `sample_id` 去重：`filter.input_merge_dedupe_by=sample_id`
- 保留策略：`filter.input_merge_dedupe_keep=first|last`（默认 `first`）
- `report.json` 会记录 `input_manifest_paths`。

1.5 guided anchor 自动补齐
- 当输入为 `synth_manifest` 且 guided 样本缺少对应 real anchor row 时，Filter 会自动尝试补齐：
  - `filter.anchor_real_manifest`
  - `clip.prompt_from_generate_config -> generate.real_manifest`
  - `input_manifest` 同级 `generate/report.json` 中的 `real_manifest`
- 补齐行为与缺失统计写入 `report.anchor_real_injection`。

2. 两个原始分数
- `s_anchor = sim(anchor_image, synthetic_image)`（仅 guided synthetic 使用；由 `semantic_pair` 提供）
- `s_prompt`（所有样本都会计算）：
  - `prompt_metric=score`：`sim(prompt_text, synthetic_image)`
  - `prompt_metric=raw_cosine`：`raw cosine in [-1, 1]`（由 cosine 映射值反算）
  - `prompt_metric=margin_norm`：`norm( score(pos_prompt) - max(score(neg_prompts)) )`

3. 一个统一总分
- `s_final = w_anchor * s_anchor + w_prompt * s_prompt`
- guided synthetic：`w_anchor=guided_w_anchor`，`w_prompt=guided_w_prompt`
- prompt-only synthetic：`w_anchor=0`，`w_prompt=1`

4. 一个分桶策略
- guided 最小资格：`s_anchor >= guided_min_anchor && s_prompt > guided_min_prompt`
- 可选：`guided_min_prompt_from_real_quantile=q05|q10|...` 时，用 real 样本 `s_prompt` 分位数覆盖 `guided_min_prompt`
- 在资格集合内按 `s_final` 排序取 Top-K 为 `accept`
- 其余样本进入 `uncertain`（Expert 审核池）
- `reject=0`（仅当 `policy.ranking_review.hard_reject=true` 时允许 reject）

## 5. 运行命令

```bash
python filter/run_filter.py \
  --config test/test-filters/configs/filter_compose.yaml
```

## 6. 快速排查

1. `guided_synth_count=0`
- 优先检查 `guide_type`：
  - `guide_type=prompt` 会视为 prompt-only
  - `guide_type=image_guided` 且 `guide_image_id` 非空时视为 guided
- 若无 `guide_type`，才回退到 `guide_image_id` 等历史 marker 字段判定。

2. `eligible_total` 偏低
- 检查 `guided_min_anchor / guided_min_prompt` 是否过严。
- 检查 guided 样本的 anchor 配对字段是否正确（`guide_image_id` 等）。

3. 出现 reject
- 检查是否开启了 `policy.ranking_review.hard_reject=true`。
