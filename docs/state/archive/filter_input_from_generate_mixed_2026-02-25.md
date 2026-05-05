# Filter 输入优先使用 Generation mixed_manifest（2026-02-25）

## Scope
- 仅调整 Filter 输入清单解析优先级。
- 不改动评分算法、策略阈值与 phase1 路由规则。

## Changes
- 更新 `filter/run_filter.py`：
  - 新增 `_resolve_filter_input_manifest(...)`。
  - Filter 输入优先级改为：
    1. `filter.input_manifest`
    2. `run_dir/generate/mixed_manifest.jsonl`（默认开启 `auto_input_from_generate_mixed=true`）
    3. `manifest_builder`
    4. stub manifest
  - `filter/report.json` 新增：
    - `input_manifest_path`
    - `input_manifest_source`
- 新增测试：
  - `test/test_filter_input_manifest_resolution.py`
  - 覆盖显式路径优先、自动使用 mixed manifest、关闭自动回退三种场景。
- 更新文档：
  - `docs/filter_quickstart.md` 新增推荐输入链路（Generation -> Filter）说明。

## Validation
```bash
python -m unittest discover -s test -p 'test_filter_input_manifest_resolution.py' -v
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
```
