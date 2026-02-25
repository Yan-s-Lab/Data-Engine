# Kernel: Filter (Phase1)

## 1. 作用

对 generation 输出进行 phase1 语义筛选，产出 `accept/reject/uncertain` 三分结果。

入口脚本：
- `filter/run_filter.py`

## 2. Phase 输入输出关系

- 输入：
  - 推荐：`<run_dir>/generate/mixed_manifest.jsonl`
  - 或显式 `filter.input_manifest`
- 输出：
  - `<run_dir>/filter/filter_scores.jsonl`
  - `<run_dir>/filter/splits/accept.jsonl`
  - `<run_dir>/filter/splits/reject.jsonl`
  - `<run_dir>/filter/splits/uncertain.jsonl`
  - `<run_dir>/filter/report.json`
- 下游关系（目标态）：
  - `accept/uncertain` 进入 annotation / HITL / training

## 3. 推荐配置

- `test/test-filters/configs/filter_compose.yaml`

## 4. 复杂配置逻辑（重点）

1. 输入清单优先级
- `filter.input_manifest`（显式）
- `<run_dir>/generate/mixed_manifest.jsonl`（默认自动）
- `manifest_builder`（启用时）
- stub manifest（兜底）

2. phase1 语义路由
- `guided synthetic`：走 `semantic_pair`
- `prompt-only synthetic`：走 `prompt_score`
- fallback：走 `semantic_anchor`
- 由 `filter.phase1_semantic.*` 控制。

3. policy 决策逻辑
- `decision=tri_gate_plus_weighted` 时：
  - 先看 gates（硬门）
  - 同时计算 `final_score`（排序/分析）

4. anchor 约束逻辑
- `semantic_anchor` 和 `anchor_ood` 依赖 real anchors。
- 若 anchors 太少，相关 stage 会降级或标记 insufficient。

## 5. 运行命令

```bash
python filter/run_filter.py \
  --config test/test-filters/configs/filter_compose.yaml
```

## 6. 快速排查

1. `guided_synth_count=0`
- 检查 manifest 是否有 `anchor_real_sample_id` 等 guided 字段。

2. `insufficient_anchor_embeddings`
- 增加 real anchors，或调整相关 gate/阈值。

3. 大量 reject
- 先检查 phase1 路由是否命中预期，再校准 gate 的 quantile/buffer。
