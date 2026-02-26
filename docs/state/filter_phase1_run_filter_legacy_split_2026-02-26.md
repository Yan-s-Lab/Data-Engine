# Filter phase1 run_filter 瘦身（legacy 模式拆分，2026-02-26）

## Scope
- 仅做代码组织重构，不改过滤行为与输出字段。
- 目标：将 `staged_clip + tri_gate` 历史兼容逻辑迁出 `run_filter.py`，避免干扰 phase1 v1 主路径阅读。

## Changes
- 新增 `filter/legacy_modes.py`
  - 承载 `run_staged_clip_filter` 及其内部辅助函数（含 tri-gate 分支）。
- 更新 `filter/run_filter.py`
  - 保留 `compose v1 / pcs_clip / stub` 主路径与公共函数。
  - `staged_clip` 分支改为调度 `filter.legacy_modes.run_staged_clip_filter`。
  - 移除已迁出的 legacy 辅助函数与 staged 具体实现。
  - 新增 `_run_filter_mode` 统一模式调度（便于回归测试）。
- 新增 `test/test_filter_mode_dispatch.py`
  - 最小回归：验证 `staged_clip` 模式确实走 legacy runner 调度。

## Validation
```bash
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
python -m unittest discover -s test -p 'test_filter_mode_dispatch.py' -v
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
```

关键结果：
- `test_filter_phase1_semantic.py`: `Ran 4 tests ... OK`
- `test_filter_mode_dispatch.py`: `Ran 1 test ... OK`
- compose 运行输出保持：`total=14, accept=8, uncertain=6, reject=0`
