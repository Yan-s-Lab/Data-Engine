# Filter Phase1 (SigLIP2) Prompt/Pair Validation（2026-02-25）

## Scope
- 仅覆盖 Filter 子阶段 phase1 语义路由实现与验证，不扩展到其他阶段。
- 对齐 `.temp/methods.tex` 与 `docs/design/phase1_semantic_routed_siglip2.md` 的当前实现路径：
  - prompt -> synthetic 语义一致性
  - real(anchor) <-> synthetic 配对语义一致性

## Changes
- 更新 `filter/run_filter.py`：
  - 新增 `_resolve_filter_prompt_text(...)`，支持在 filter 侧复用 generation 的 prompt 来源，优先级：
    1. `filter.clip.prompt_text`
    2. `filter.clip.prompt_template_file`
    3. `filter.clip.prompt_from_generate_config` -> `generate.comfyui.prompt.template_file|text_template|text`
  - 在 `report.json` 中新增 `prompt_text_source`，用于追踪 phase1 的 prompt 实际来源。
- 新增测试 `test/test_filter_phase1_semantic.py`：
  - 验证 phase1 路由：
    - guided synthetic -> `semantic_pair`
    - prompt-only synthetic -> `prompt_score`
    - paired miss -> `semantic_anchor` fallback
  - 验证可从 generation 配置中的 `template_file` 读取 prompt 文本并注入 filter 配置。

## Validation
```bash
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
```
