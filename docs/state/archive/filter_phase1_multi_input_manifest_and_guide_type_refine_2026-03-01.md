# Filter refine：多 generation 输入合并 + guide_type 路由判定（2026-03-01）

## Scope
- 针对当前 generation `synth_manifest.jsonl` 字段口径，收敛 Filter phase1 输入与 guided 判定。
- 不修改 generation/training 阶段。

## Changes
- `filter/run_filter.py`
  - 新增 `filter.input_manifests` 配置解析（多 manifest 输入，按顺序读取合并）。
  - 保留 `filter.input_manifest` 与自动发现逻辑，作为兼容路径。
  - 新增输入合并去重配置：
    - `filter.input_merge_dedupe_by`（默认 `sample_id`）
    - `filter.input_merge_dedupe_keep`（`first|last`，默认 `first`）
  - `report.json` 新增 `input_manifest_paths` 字段。
  - guided 判定优先读取 `guide_type`：
    - `prompt` -> prompt-only
    - `image_guided` 且 `guide_image_id` 非空 -> guided
    - 无 `guide_type` 时回退历史 marker 字段。
  - manifest 归一化补充 `guide_image -> guide_image_id` 兼容映射。
  - anchor real manifest 自动发现支持多 input manifest 的同级 `report.json` 扫描。
- `test/test_filter_input_manifest_resolution.py`
  - 新增 `input_manifests` 解析单测。
- `test/test_filter_phase1_semantic.py`
  - 新增 `guide_type` 路由优先级单测。
- `docs/kernels/filter_phase1.md`
  - 更新多输入与 `guide_type` 判定规则文档。

## Validation
```bash
python -m unittest discover -s test -p 'test_filter_input_manifest_resolution.py' -v
python -m unittest discover -s test -p 'test_filter_phase1_semantic.py' -v
```
