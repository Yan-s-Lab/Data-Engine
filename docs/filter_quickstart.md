# Filter Quickstart（兼容入口）

主文档索引：
- [docs/README_PIPELINE_ZH.md](/home/yan/StudioSpace/DataEngine/docs/README_PIPELINE_ZH.md)

Filter phase1 分文档：
- [docs/kernels/filter_phase1.md](/home/yan/StudioSpace/DataEngine/docs/kernels/filter_phase1.md)

当前约束：
- `filter/run_filter.py` 仅支持 `filter.mode=compose`（phase1 v1）。

最简运行：
```bash
python filter/run_filter.py \
  --config test/test-filters/configs/filter_compose.yaml
```
