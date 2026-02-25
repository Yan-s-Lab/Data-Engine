# Filter Quickstart（单模块）

本文档只覆盖 `filter` 模块本身，不跑整条 `dataloader -> generate -> filter -> train -> eval` 流水线。

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

### 3.1 PCS-CLIP（快速 smoke）

```bash
python filter/run_filter.py \
  --config artifacts/testfilter/configs/filter_pcs_clip.yaml
```

### 3.2 Staged CLIP（分层指标）

```bash
python filter/run_filter.py \
  --config artifacts/testfilter/configs/filter_staged_clip.yaml
```

### 3.3 Compose（可组合策略）

```bash
python filter/run_filter.py \
  --config artifacts/testfilter/configs/filter_compose.yaml
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
`artifacts/testfilter/runs/testfilter_compose/filter/`

关键输出：
- `manifest_in.jsonl`
- `filter_scores.jsonl`
- `splits/accept.jsonl`
- `splits/reject.jsonl`
- `splits/uncertain.jsonl`
- `report.json`

## 6. 排查要点

1. `anchor_ood.enabled=false` 且 `reason=insufficient_anchor_embeddings`
- 真实 anchor 太少（常见于小样本 smoke），先增加 real 样本数量

2. `guided_synth_count=0`
- synthetic 行没有命中 `phase1_semantic.guided_marker_fields`
- 检查 manifest 是否有 `anchor_real_sample_id` 等字段

3. `s_phase1_semantic` 很低导致大面积 reject
- 先放宽 gate（例如调低 quantile 或增加 buffer）
- 再检查 prompt 质量与 `prompt_field` 是否有效

## 7. 自动生成 `input_manifest.jsonl`（不手写）

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
