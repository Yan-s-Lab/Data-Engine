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

SigLIP2 标注集阈值评估（raw logits + margin + F1 threshold sweep）：
```bash
python filter/evaluate_siglip2_margin_threshold.py \
  --config configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline.yaml \
  --top-k 3
```

若希望控制误收，可加 precision 约束（例如 `precision>=0.9` 时召回最大）：
```bash
python filter/evaluate_siglip2_margin_threshold.py \
  --config configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline.yaml \
  --top-k 3 \
  --min-precision 0.9
```

正式过滤（读取 `filter.input_manifests`，使用外部阈值）：
```bash
python filter/filter_stages/filter1/main.py \
  --config configs/coco_pose_2017__expansion/filter/body_pose_coco_filter_pipiline.yaml \
  --threshold-report artifacts/tmp/siglip2_margin_threshold_report.json \
  --top-k 3
```
默认输出目录：`artifacts_root/run_id/filter`（同时会解析/创建 `pipeline` 与 `pipline` 目录）。
