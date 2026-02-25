# Generate 锚图尺寸过滤跳过（2026-02-25）

## Scope
- 在 ComfyUI 生成阶段增加“超尺寸锚图跳过”能力。
- 目标是让不符合阈值的 real image 不参与引导生成，避免大图导致长时间卡顿/OOM。

## Changes
- 更新 `synth/run_generate.py`：
  - 新增 `generate.comfyui.anchor_filter` 配置解析。
  - 新增按尺寸过滤锚图逻辑（支持 `max_width` / `max_height` / `max_long_edge`）。
  - 对超阈值锚图直接跳过，不进入提交队列。
  - 过滤统计写入 `generate/report.json`：
    - `anchor_filter_enabled`
    - `anchor_total_count`
    - `anchor_eligible_count`
    - `anchor_skipped_count`
    - `anchor_filter_max_*`
- 更新 managed 示例配置：
  - `configs/examples/comfyui_generate_from_norm_yk001_prompt_canny_managed.yaml`
  - 增加 `generate.comfyui.anchor_filter.max_long_edge: 1536`
- 更新文档：
  - `docs/README_PIPELINE_ZH.md` 新增 anchor_filter 用法说明。
- 新增测试：
  - `test/test_generate_anchor_filter.py`

## Validation
```bash
python -m unittest discover -s test -p 'test_generate_anchor_filter.py' -v
```
