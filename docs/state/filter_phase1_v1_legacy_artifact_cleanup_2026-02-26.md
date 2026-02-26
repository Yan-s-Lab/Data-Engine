# Filter Phase1 v1 过时产物清理（2026-02-26）

## Scope
- 仅清理 phase1 v1 下的历史残留输出，避免指标字段混淆。

## Changes
- `filter/run_filter.py`
  - 在 `filter.mode=compose` 运行开始时，若存在历史 `phase1_compare_log.jsonl`，自动删除。
  - `report.json` 新增 `legacy_artifacts_removed`，显式记录被清理的历史文件路径。

## Validation
```bash
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
```

关键结果：
- 运行后 `test/test-filters/runs/testfilter_compose/filter/phase1_compare_log.jsonl` 不再存在。
- `report.json.legacy_artifacts_removed` 包含该文件路径。
- 单测通过。
