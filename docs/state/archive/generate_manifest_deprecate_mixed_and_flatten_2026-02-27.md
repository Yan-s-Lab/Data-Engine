# Generation 清理：弃用 mixed_manifest + 扁平 synth 字段（2026-02-27）

## Scope
- 仅收敛 generation 默认产物与字段。
- mixed_manifest 彻底弃用，不再由 `synth/run_generate.py` 生成。

## Changes
- `synth/run_generate.py`
  - 仅写 `generate/synth_manifest.jsonl` 与 `generate/report.json`。
  - 删除 `mixed_manifest.jsonl` 与 trace mixed 产物写入。
  - `generate.manifest.guide_type` 改为手动配置（`prompt|image_guided`），并做枚举校验。
  - core synth manifest 字段调整为：
    - `synthetic_id`
    - `synthetic_image_name`
    - `synthetic_image_path`
    - `width`, `height`
    - `prompt_text`, `seed`
    - `guide_type`
    - `config_ref`
    - `synthetic_image_ids`
  - 删除输出字段：`sample_id`, `source`, `image_path`, `guide_image`, `anchor_real_sample_id`。
- `pipelines/run_yaml_pipeline.py`
  - generate 阶段关键产物改为 `generate/synth_manifest.jsonl`。
  - filter 默认输入改为 `generate/synth_manifest.jsonl`。
- `filter/run_filter.py`
  - 自动发现优先：`run_dir/generate/synth_manifest.jsonl`（保留 mixed 兼容回退）。
  - 增加新 schema 兼容映射：`synthetic_id -> sample_id`、`synthetic_image_path -> image_path`、`source` 默认 synthetic。

## Config
- `configs/examples/comfyui_generate_from_norm_yk003_prompt_only_managed.yaml`
  - 新增 `generate.manifest.guide_type: prompt`。

## Docs
- 更新：
  - `docs/kernels/control_generation.md`
  - `docs/kernels/filter_phase1.md`
  - `docs/README_PIPELINE_ZH.md`
  - `docs/state/data_engine_state.md`

## Validation
- `python -m py_compile synth/run_generate.py filter/run_filter.py pipelines/run_yaml_pipeline.py`
- `python -m unittest discover -s test -p 'test_generate_manifest_profile.py' -v`
- `python -m unittest discover -s test -p 'test_filter_input_manifest_resolution.py' -v`
