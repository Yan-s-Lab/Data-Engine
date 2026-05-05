# Filter Phase1 比较日志与模板 Prompt 对齐（2026-02-25）

## Scope
- 仅改 Filter phase1 可观测性与测试配置，不改策略目标。

## Changes
- `filter/filter_stages/clip_embed_cache.py`
  - 文本输入增加 `truncation=True`，并按模型 `max_position_embeddings` 截断，避免长模板 prompt 触发 SigLIP2 长度报错。
- `filter/filter_stages/clip_semantic_anchor.py`
  - `compute_paired_anchor_semantic_scores` 增加配对调试字段：
    - `anchor_sid_resolved`
    - `pair_miss_reason`
- `filter/run_filter.py`
  - compose 模式新增输出 `phase1_compare_log.jsonl`（每样本一条）：
    - compare 类型（anchor image / prompt text / anchor set）
    - compare target
    - phase1 分数与子分数
    - gate 检查细节（含阈值与 pass/fail）
    - 备注 remark
  - `filter_scores.jsonl` 增加 `gate_checks`。
  - `report.json -> phase1_semantic` 增加：
    - `compare_log_path`
    - `compare_log_count`
- `test/test-filters/configs/filter_compose.yaml`
  - `filter.clip.prompt_template_file: ../../../configs/examples/arm_deltoid_template.txt`
  - 使用模板作为评估 prompt，不再手写短文本。

## Validation
```bash
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
```

关键结果：
- `report.json` 中 `prompt_text_source = clip.prompt_template_file`
- `phase1_semantic.compare_log_path` 指向 `filter/phase1_compare_log.jsonl`
- `phase1_semantic.compare_log_count = 14`
