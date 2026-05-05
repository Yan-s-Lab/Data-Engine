# Filter refine：task_body_generation 正式产物接续执行（2026-02-28）

## Scope
- 目标：在 `configs/task_body_generation` generation 已完成后，继续执行 Filter phase1。
- 仅改 Filter phase1 输入衔接与可解释性，不改 generation / training。

## 发现的问题（baseline）
- 直接使用 `generate/synth_manifest.jsonl` 运行时：
  - `guided_anchor_hit_count=0`
  - `paired.pair_hit_count=0`
  - `eligible_total=0`
  - 全量进入 `uncertain`。
- 原因：`synth_manifest` 不含 real anchor 行，`guide_image_id` 无法在当前输入内找到 anchor embedding。
- 额外问题：`prompt_from_generate_config` 读取 `template_file` 时，对仓库根相对路径（如 `configs/...`）解析不稳。

## 实施改动
- `filter/run_filter.py`
  - 新增 `_resolve_path_with_workspace_fallback(...)`：支持“配置目录相对 + 仓库根相对”双路径解析。
  - 新增 `_resolve_anchor_real_manifest(...)`：anchor real manifest 自动解析来源：
    1. `filter.anchor_real_manifest`
    2. `clip.prompt_from_generate_config -> generate.real_manifest`
    3. `input_manifest` 同级 `generate/report.json.real_manifest`
  - 新增 `_inject_anchor_real_rows(...)`：对 guided synthetic 自动补齐缺失 real anchor rows。
  - `report.json` 新增：
    - `input_total`（补锚前输入数）
    - `anchor_real_injection`（补锚来源、补入数量、未解析数量）
  - 删除 `build_phase1_semantic_scores` 未使用参数 `semantic_scores`，简化接口。
- `test/test_filter_phase1_semantic.py`
  - 适配函数签名。
  - 新增补锚行为测试：`test_inject_anchor_rows_from_explicit_real_manifest`。
- 新增正式 Filter 配置：
  - `configs/task_body_generation/filter/body_pose_prompt_canny_phase1.yaml`

## 运行验证
```bash
conda run -n dataengine python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
conda run -n dataengine python -m unittest discover -s test -p 'test_filter_input_manifest_resolution.py' -v
conda run -n dataengine python filter/run_filter.py --config configs/task_body_generation/filter/body_pose_prompt_canny_phase1.yaml
```

## 关键结果（refine 后）
- 输出目录：`artifacts/user_runs/yk003_body_pose_prompt_canny_filter_phase1_20260228/filter`
- `report.json` 关键项：
  - `input_total=69`
  - `total=138`（自动补入 69 条 real anchor）
  - `anchor_real_injection.injected_anchor_count=69`
  - `phase1_semantic.guided_anchor_hit_count=69`
  - `ranking_review.eligible_total=67`
  - `accept=89`（含 `keep_real_always` 的 real=69 与 synthetic top-20）
  - `uncertain=49`
  - `reject=0`
