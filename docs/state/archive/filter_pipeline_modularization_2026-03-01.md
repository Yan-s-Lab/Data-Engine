# Filter 重构：pipeline 模块化与 phase 调度抽象（2026-03-01）

## Scope
- 按当前需求，将 `run_filter.py` 从算法堆叠改为入口调度器。
- 实现“配置驱动 phase 链路 + 算法模块解耦 + 输入输出职责分离”。
- 保持当前可运行策略为 `phase1_dual_signal`。

## Changes
- 新增 `filter/pipeline_engine/io_ops.py`
  - 输入处理与补锚逻辑集中：
    - prompt 解析
    - input manifest 解析/合并/去重
    - row 归一化
    - guided anchor real rows 注入
- 新增 `filter/pipeline_engine/phase1_dual_signal.py`
  - phase1 算法模块独立：
    - `compute_phase1_score_rows`
    - `apply_dual_signal_selection`
    - `run_phase`
- 新增 `filter/pipeline_engine/orchestrator.py`
  - phase 调度器：
    - 支持 `filter.pipeline.phases` 配置序列
    - 通过 phase id 注册表运行
    - 逐级执行并汇总 pipeline report
- 新增 `filter/pipeline_engine/__init__.py`
- 重写 `filter/run_filter.py`
  - 仅保留：配置加载、输入装配、调用 pipeline、输出 artifacts。
  - 保留少量兼容导出函数供现有测试调用。
- 更新配置：
  - `configs/task_body_generation/filter/body_pose_prompt_canny_phase1.yaml`
  - 新增 `filter.pipeline.phases` 示例（phase1_dual_signal）
- 更新文档：
  - `docs/kernels/filter_phase1.md`

## Validation
```bash
conda run -n dataengine python -m py_compile \
  filter/run_filter.py \
  filter/pipeline_engine/io_ops.py \
  filter/pipeline_engine/phase1_dual_signal.py \
  filter/pipeline_engine/orchestrator.py \
  test/test_filter_phase1_semantic.py \
  test/test_filter_input_manifest_resolution.py

conda run -n dataengine python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
conda run -n dataengine python -m unittest discover -s test -p 'test_filter_input_manifest_resolution.py' -v
```

## Result
- `filter/run_filter.py` 已从 1009 行收敛为 112 行入口。
- 核心复杂度迁移到可复用模块，phase 组合扩展点明确。
