# Filter Phase1 收敛为 compose-only（2026-02-26）

## Scope
- 按当前方法收敛 filter phase1，移除旧设计路径。
- 仅保留最简 phase1 v1 主流程，不引入新算法。

## Changes
- `filter/run_filter.py`
  - 删除旧模式实现与调度：`stub`/`pcs_clip`/`staged_clip`。
  - 删除旧 `pcs_clip` 相关函数（扰动、CLIP单独打分等）。
  - 入口仅支持 `filter.mode=compose`；其他 mode 直接报错。
  - 保留并继续使用 phase1 v1 核心：`s_anchor`、`s_prompt`、`s_final` + Top-K 审核池。

- 删除遗留文件
  - `filter/legacy_modes.py`
  - `test/test_filter_mode_dispatch.py`

- 文档同步
  - 更新 `docs/state/data_engine_state.md` 中 filter 能力描述为 compose-only。

## Validation
```bash
python -m py_compile filter/run_filter.py
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
```

关键结果：
- `test_filter_phase1_semantic.py`: `Ran 4 tests ... OK`
- compose 运行维持：`total=14, accept=8, uncertain=6, reject=0`
