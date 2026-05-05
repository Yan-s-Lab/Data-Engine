# Filter phase1 重构：dual-signal（text-image + image-image）（2026-03-01）

## Scope
- 按当前需求重做 phase1 决策逻辑。
- 去除旧的 Top-K ranking_review 决策路径在 task 配置中的依赖。
- 保留输入拼接、anchor 自动补齐、guided 路由判定等基础能力。

## Changes
- `filter/run_filter.py`
  - 新增 `_apply_dual_signal_selection(...)`。
  - `policy.decision=phase1_dual_signal` 时启用新决策：
    - prompt-only: 只看 `s_prompt`。
    - guided: 同时看 `s_prompt` 和 `s_anchor`。
    - 支持 `missing_pair_policy` 与 `hard_reject`。
  - dual-signal 启用时，SigLIP 模型默认使用 `siglip_sigmoid` 作为 prompt 打分口径。
  - `filter_scores.jsonl` 新增 `s_anchor_hit` 字段，显式表示 image-image 配对命中。
- `configs/task_body_generation/filter/body_pose_prompt_canny_phase1.yaml`
  - 切换到 `policy.decision: phase1_dual_signal`。
  - 新增 `phase1_dual_signal` 阈值配置。
  - `clip.prompt_score_mode` 改为 `siglip_sigmoid`。
  - `phase1_semantic.prompt_metric` 改为 `score`。
- `test/test_filter_phase1_semantic.py`
  - 新增 dual-signal 决策单测（guided/prompt-only/missing-pair）。
- `docs/kernels/filter_phase1.md`
  - 更新为 dual-signal 口径说明。

## Validation
```bash
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
```
