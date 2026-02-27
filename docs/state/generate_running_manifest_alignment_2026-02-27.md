# Generation 计数语义最小收敛（2026-02-27）

## Scope
- 仅修正 generation 报告中的计数语义。
- 不新增阶段产物，不改变现有 `synth_manifest.jsonl` 逐图结构。

## Changes
- `synth/run_generate.py`
  - 在 `report.json` 新增 `synthetic_job_count`。
  - 计算规则：优先按 `comfy_prompt_id` 去重计数（ComfyUI running 数）；若无该字段则回退为逐图计数。
- `docs/kernels/control_generation.md`
  - 补充 `synthetic_count` 与 `synthetic_job_count` 的语义区别。

## Notes
- `synth_manifest.jsonl` 继续按图片落盘，兼容现有 filter 输入。
- `synthetic_image_ids` 继续表示该图所属 running 的同批输出集合。

## Validation
- `python -m py_compile synth/run_generate.py`
- `conda run -n dataengine python -m unittest discover -s test -p 'test_generate_manifest_profile.py' -v`
