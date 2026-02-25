# Kernel: DataLoader (Norm)

## 1. 作用

把 raw real 数据标准化为后续 phase 可消费的 `real_manifest.jsonl`，并统一命名/格式。

入口脚本：
- `ingest/run_dataloader.py`

## 2. Phase 输入输出关系

- 输入：
  - `dataloader.image_dir` 下图片
  - 可选 `dataloader.label_dir` 下标注
- 输出：
  - `<run_dir>/dataloader/real_manifest.jsonl`
  - `<run_dir>/dataloader/anchor_stats.json`
  - `<run_dir>/dataloader/report.json`
- 下游关系：
  - `generation` 读取 `real_manifest.jsonl` 作为 `generate.real_manifest`

## 3. 推荐配置

- 本地单阶段：
  - `configs/examples/dataloader_norm_test_generation_yk002.yaml`
- 托管/串行计划：
  - `configs/examples/dataloader_norm_test_generation_yk002_managed.yaml`

## 4. 复杂配置逻辑（重点）

1. 输出目录逻辑
- 若配置了 `dataloader.output.root_dir`，写入该目录。
- 否则默认写入 `<run_dir>/dataloader/normalized`。

2. 命名/重命名逻辑
- `dataloader.naming.filename_template` 存在时，优先模板命名。
- 否则 `canonicalize_names=true` 时使用规范名。
- `target_image_ext` 可触发格式转换（如 jpg -> png）。

3. 标签约束逻辑
- `require_labels=true` 且缺 label 的样本会被跳过。
- 最终若全部跳过会报错退出。

## 5. 运行命令

```bash
python ingest/run_dataloader.py \
  --config configs/examples/dataloader_norm_test_generation_yk002.yaml
```

## 6. 快速排查

1. `no images found`
- 检查 `image_dir` 与 `patterns`。

2. `label_dir not found` 或大量缺 label
- 检查 `label_dir`、`label_ext` 与 `require_labels`。

3. `duplicate output stem`
- 检查 `filename_template` 是否把多个样本映射成同名。
