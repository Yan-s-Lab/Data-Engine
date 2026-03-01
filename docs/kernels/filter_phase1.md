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

## 4. Phase1（Dual Signal）

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

2. 两个原始分数（仅保留）
- `s_prompt`（text vs image）：
  - SigLIP2 路径固定为 `logits_per_image -> sigmoid`，范围 `[0,1]`
- `s_anchor`（image vs image）：
  - `sim(anchor_image, synthetic_image)`（仅 guided synthetic 使用；由 `semantic_pair` 提供）

3. 决策策略（`policy.decision=phase1_dual_signal`）
- guided synthetic：
  - accept: `s_prompt >= prompt_accept_threshold && s_anchor >= pair_accept_threshold`
  - 否则进入 uncertain（或 `hard_reject=true` 时按 uncertain 阈值 reject）
- prompt-only synthetic：
  - accept: `s_prompt >= prompt_accept_threshold`
  - 否则进入 uncertain（或 `hard_reject=true` 且低于 uncertain 阈值时 reject）
- pair 缺失策略：
  - `missing_pair_policy=uncertain|reject`

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

2. accept 过少
- 检查 `phase1_dual_signal.prompt_accept_threshold / pair_accept_threshold` 是否过严。
- 检查 guided 样本的 anchor 配对字段是否正确（`guide_image_id` 等）。

3. 出现 reject
- 检查是否开启了 `phase1_dual_signal.hard_reject=true`，以及 `missing_pair_policy=reject`。
