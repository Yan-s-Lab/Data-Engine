# Clean Synthetic Manifest（基于 `data/comfyui/output`，2026-02-26）

## Scope
- 按用户确认的新口径生成 synthetic 主清单：
  - synthetic 只认 `data/comfyui/output`
  - `synth_manifest.jsonl` 仅作 real->synthetic 映射参考
- 不改 generation/filter 逻辑。

## New Script
- `synth/build_clean_synth_manifest.py`
- 输入：
  - `--output-dir`（默认 `data/comfyui/output`）
  - 多个 `--synth-manifest`
- 输出：
  - `--out-jsonl`（clean manifest）
  - `--out-summary`（统计摘要）

## Mapping Rules
1. 精确匹配：`output filename == synth_manifest.comfy_filename`
2. 前缀回退（仅 temp 风格，典型 canny）：
   - 使用 `effective_filename_prefix` 匹配 `real_xxx_canny_00001_.png` 这类文件
   - 当多个 run 都有同一 prefix 时，优先选择该 prefix 参考条目更多的 run；同数时取命令行中靠后的 manifest
3. 未匹配到参考条目的输出图：`map_status=no_reference`

## Command
```bash
python synth/build_clean_synth_manifest.py \
  --synth-manifest artifacts/runs/yk003_prompt_only_demo_managed_20260225_rerun/generate/synth_manifest.jsonl \
  --synth-manifest artifacts/runs/yk003_prompt_canny_demo_managed_20260225_rerun/generate/synth_manifest.jsonl \
  --synth-manifest artifacts/runs/yk003_prompt_canny_demo_managed_20260225_2_rerun/generate/synth_manifest.jsonl \
  --out-jsonl artifacts/user_runs/clean_synth_manifest_2026-02-26.jsonl \
  --out-summary artifacts/user_runs/clean_synth_manifest_2026-02-26.summary.json
```

## Result
- `output_image_count=1052`
- `matched_exact_count=131`（主要是 prompt_only）
- `matched_prefix_count=345`（主要是 canny temp->prefix 映射）
- `matched_total_count=476`
- `no_reference_count=576`
- `ambiguous_prefix_count=61`

## Output Artifacts
- `artifacts/user_runs/clean_synth_manifest_2026-02-26.jsonl`
- `artifacts/user_runs/clean_synth_manifest_2026-02-26.summary.json`
