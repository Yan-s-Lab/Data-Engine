# Filter Quickstart（单模块）

本文档只覆盖 `filter` 模块本身。当前推荐链路是 `dataloader -> generate -> filter(phase1)`。

## 1. 入口关系（避免混淆）

- 全链路入口：`pipelines/run_yaml_pipeline.py`
  - 当 `pipeline.steps` 包含 `filter` 时，内部会调用 `filter/run_filter.py`
- Filter 单模块入口：`filter/run_filter.py`
  - 仅执行过滤阶段，直接产出 `filter` 目录工件

## 2. 最小执行命令

在仓库根目录执行：

```bash
python filter/run_filter.py --config <your_filter_config.yaml>
```

当前脚本 CLI 只需要一个参数：
- `--config`：配置文件路径

## 3. 推荐配置与命令

当前保留并推荐的 filter 配置为 compose：

```bash
python filter/run_filter.py \
  --config test/test-filters/configs/filter_compose.yaml
```

## 4. SigLIP2 + Phase1 路由（compose）

若你希望在 compose 模式里使用 SigLIP2 并启用 phase1 语义路由，关键配置如下：

```yaml
filter:
  mode: compose
  clip:
    model_id: google/siglip2-base-patch16-224
    prompt_score_mode: siglip_sigmoid
  phase1_semantic:
    enabled: true
    guided_source: semantic_pair
    prompt_only_source: prompt_score
    fallback_source: semantic_anchor
```

## 5. 输出工件

`run.run_id` + `run.artifacts_root` 会决定输出目录，例如：
`test/test-filters/runs/testfilter_compose/filter/`

关键输出：
- `manifest_in.jsonl`
- `filter_scores.jsonl`
- `splits/accept.jsonl`
- `splits/reject.jsonl`
- `splits/uncertain.jsonl`
- `report.json`

## 6. 推荐输入链路（Generation -> Filter）

推荐让 Filter 直接读取 generation 阶段的 `mixed_manifest.jsonl`，而不是通过文件名重建：

```yaml
run:
  run_id: your_run_id
  artifacts_root: artifacts/runs

filter:
  mode: compose
  # 可选：不写时会自动尝试 run_dir/generate/mixed_manifest.jsonl
  # input_manifest: artifacts/runs/your_run_id/generate/mixed_manifest.jsonl
  auto_input_from_generate_mixed: true
```

`run_filter.py` 的输入优先级：
1. `filter.input_manifest`（显式指定）
2. `run_dir/generate/mixed_manifest.jsonl`（默认自动启用）
3. `manifest_builder`（当启用且满足触发条件）
4. stub manifest（仅无输入时兜底）

说明：`filter_pcs_clip.yaml` / `filter_staged_clip.yaml` 的旧路径（`artifacts/testfilter/configs/`）已不再作为当前文档路径。

## 7. 排查要点

1. `anchor_ood.enabled=false` 且 `reason=insufficient_anchor_embeddings`
- 真实 anchor 太少（常见于小样本 smoke），先增加 real 样本数量

2. `guided_synth_count=0`
- synthetic 行没有命中 `phase1_semantic.guided_marker_fields`
- 检查 manifest 是否有 `anchor_real_sample_id` 等字段

3. `s_phase1_semantic` 很低导致大面积 reject
- 先放宽 gate（例如调低 quantile 或增加 buffer）
- 再检查 prompt 质量与 `prompt_field` 是否有效

## 8. 自动生成 `input_manifest.jsonl`（不手写，兜底方案）

`filter/run_filter.py` 支持在读取输入前自动构建 manifest：

```yaml
filter:
  input_manifest: test/test-filters/input_manifest.jsonl
  manifest_builder:
    enabled: true
    force_rebuild: true
    filename_driven:
      enabled: true
      roots: [test/test-filters/real_raw, test/test-filters/synthetic]
      patterns: ["**/*.png", "**/*.jpg", "**/*.jpeg"]
      real:
        sample_id_template: "{stem}_real"
      synthetic:
        stem_pattern: "^(?P<anchor>.+)_[^_]+_[0-9]+$"
        anchor_template: "{anchor}_real"
```

行为说明：
- 先按 `roots + patterns` 扫描图片
- 文件名匹配 `synthetic.stem_pattern` 的行标记为 `source=synthetic`
- 未匹配的行标记为 `source=real`
- synthetic 的 `anchor_real_sample_id` 用 `anchor_template` 从正则分组渲染
