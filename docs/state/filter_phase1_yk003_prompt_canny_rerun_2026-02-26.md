# Filter phase1 运行：yk003 prompt+canny rerun（2026-02-26）

## Scope
- 按当前用户请求执行一次 Filter phase1。
- 输入固定为：
  - `artifacts/runs/yk003_prompt_canny_demo_managed_20260225_2_rerun/generate/mixed_manifest.jsonl`
- 不改 filter 代码逻辑，仅新增运行配置并执行。

## Config
- 新增配置：
  - `configs/examples/filter_phase1_yk003_prompt_canny_rerun.yaml`
- 关键设置：
  - `filter.mode: compose`
  - `filter.input_manifest`: 指向上述 yk003 canny rerun 的 mixed manifest
  - `clip.model_id: google/siglip2-base-patch16-224`
  - `phase1_semantic.prompt_metric: raw_cosine`
  - `policy.ranking_review.keep_top_ratio: 0.3`
- 输出 run 目录（可写目录）：
  - `artifacts/user_runs/yk003_prompt_canny_demo_managed_20260225_2_rerun_filter_phase1_20260226`

## Execution
```bash
conda run -n dataengine python filter/run_filter.py \
  --config configs/examples/filter_phase1_yk003_prompt_canny_rerun.yaml
```

## Result Summary
- `total=476`
- `accept=175`
- `uncertain=301`
- `reject=0`
- `accept_ratio=0.3676`
- `phase1_semantic.guided_synth_count=345`
- `phase1_semantic.guided_anchor_hit_count=345`
- `ranking_review.eligible_total=145`
- `ranking_review.keep_count=44`

## Output Artifacts
- `artifacts/user_runs/yk003_prompt_canny_demo_managed_20260225_2_rerun_filter_phase1_20260226/filter/filter_scores.jsonl`
- `artifacts/user_runs/yk003_prompt_canny_demo_managed_20260225_2_rerun_filter_phase1_20260226/filter/splits/accept.jsonl`
- `artifacts/user_runs/yk003_prompt_canny_demo_managed_20260225_2_rerun_filter_phase1_20260226/filter/splits/reject.jsonl`
- `artifacts/user_runs/yk003_prompt_canny_demo_managed_20260225_2_rerun_filter_phase1_20260226/filter/splits/uncertain.jsonl`
- `artifacts/user_runs/yk003_prompt_canny_demo_managed_20260225_2_rerun_filter_phase1_20260226/filter/report.json`
