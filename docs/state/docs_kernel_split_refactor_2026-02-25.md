# 文档体系重构：主文档 + Kernel 分文档（2026-02-25）

## Scope
- 重构文档结构，不改 pipeline 代码逻辑。
- 目标：
  - 主文档只保留架构/编排/索引。
  - 分文档承载 kernel 技术细节、脚本运行、配置说明。
  - 在主文档明确 phase 产出与下阶段消费关系。

## Changes
- 重写主文档：
  - `docs/README_PIPELINE_ZH.md`
  - 新增 `MVP 目标链路`、`当前已稳定边界`、`phase 产物流转表`、`kernel 分文档索引`
- 新增 kernel 分文档：
  - `docs/kernels/dataloader_norm.md`
  - `docs/kernels/control_generation.md`
  - `docs/kernels/filter_phase1.md`
- 兼容入口处理：
  - `docs/filter_quickstart.md` 改为跳转到新索引与 filter kernel 文档
- 同步入口说明：
  - `README.md`
  - `docs/data_flow.md`

## Validation
已通过：
- `python ingest/run_dataloader.py --config configs/examples/dataloader_norm_test_generation_yk002.yaml`
- `python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml`
- `python -m unittest discover -s test -p 'test_generate_anchor_filter.py' -v`
- `python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v`

受环境/历史问题影响：
- generation 最小 smoke（临时 `max_synth_samples=1`）进程超时未完成，已中止；ComfyUI API 可达（`/system_stats` 可返回）。
- `test_dataloader_pipeline_smoke.py` 当前失败（测试夹具路径指向 `test/testfilter/...`），属于已有测试数据路径不一致问题。
