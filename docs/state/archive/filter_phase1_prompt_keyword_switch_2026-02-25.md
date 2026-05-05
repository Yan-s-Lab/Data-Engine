# Filter Phase1 评估 Prompt 切换为关键词短句（2026-02-25）

## Scope
- 仅调整 `test/test-filters` 的 filter 评估 prompt 配置。

## Changes
- 更新 `test/test-filters/configs/filter_compose.yaml`：
  - 从 `clip.prompt_template_file` 切换为 `clip.prompt_text`
  - 采用关键词短句：
    - `a realistic photo of a human upper arm with clearly visible deltoid muscle, complete upper arm anatomy, and natural body proportion`

## Validation
```bash
python filter/run_filter.py --config test/test-filters/configs/filter_compose.yaml
```

关键结果：
- `report.json.prompt_text_source = clip.prompt_text`
- phase1 路由统计保持：guided=7、prompt-only=5
