# Kernel: Control Generation

## 1. 作用

基于 real anchors manifest + ComfyUI workflow 生成 synthetic，并输出可直接给 filter 的 `mixed_manifest.jsonl`。

入口脚本：
- `synth/run_generate.py`

## 2. Phase 输入输出关系

- 输入：
  - `generate.real_manifest`（来自 dataloader）
  - `generate.comfyui.workflow`（API prompt graph）
  - prompt/seed/control 配置
- 输出（默认 `manifest.profile=core`）：
  - `<run_dir>/generate/synth_manifest.jsonl`（核心追踪字段）
  - `<run_dir>/generate/mixed_manifest.jsonl`（核心追踪字段，real+synth）
  - `<run_dir>/generate/report.json`
- 下游关系：
  - `filter` 推荐直接读取 `mixed_manifest.jsonl`

## 3. 推荐配置

- prompt-only：
  - `configs/examples/comfyui_generate_from_norm_yk001_prompt_only_managed.yaml`
- prompt+canny：
  - `configs/examples/comfyui_generate_from_norm_yk001_prompt_canny_managed.yaml`

## 4. 复杂配置逻辑（重点）

1. Workflow 源
- 二选一：`generate.comfyui.workflow` 或 `generate.comfyui.prompt_graph`。
- `workflow` 文件必须是 ComfyUI API graph（不是 UI workflow JSON）。

2. prompt 注入逻辑
- 支持 `text` / `text_template` / `template_file`。
- 若配置 `template_file`，会读取文件内容作为 prompt 模板来源。
- `render_template=true` 时会按样本变量渲染模板。

3. anchor 注入逻辑
- `anchor_images[]` 可配置多路控制图注入。
- 每一路可独立设定 `node_id/input_key/path_field/upload`。

4. 执行/超时逻辑
- `non_blocking + max_inflight` 控制并发提交。
- `on_timeout=fail|skip|retry` 与 `timeout_retries` 控制超时策略。

5. 文件名前缀逻辑
- `filename_prefix.template` 可使用 `anchor_image_stem`、`sample_index`、`seed` 等变量。

6. manifest 分层（core vs capabilities）
- `generate.manifest.profile: compat|core`（默认 `core`）
  - `core`：`synth_manifest/mixed_manifest` 使用最小追踪字段（默认）。
  - `compat`：按需回退到历史全字段。
- `generate.manifest.write_trace_artifacts`（默认 `false`）：
  - 写 `synth_trace_manifest.jsonl`、`mixed_trace_manifest.jsonl`。
- `generate.comfyui.persist_outputs`（默认 `false`）：
  - `false`：优先直接引用 `generate.comfyui.output_dir` 下的 ComfyUI 输出文件，不再复制到 `<run_dir>/generate/images`。
  - `true`：下载并保存到 `<run_dir>/generate/images`。

核心追踪字段（trace）：
- `sample_id`, `source`, `image_path`
- `prompt_text`, `seed`
- `guide_image`, `guide_type`
- `width`, `height`
- `config_ref`
- `synthetic_image_ids`（同一个 ComfyUI prompt job 的输出 sample_id 数组）
- `anchor_real_sample_id`（可选；存在时写入）

## 5. 运行命令

```bash
python synth/run_generate.py \
  --config configs/examples/comfyui_generate_from_norm_yk001_prompt_only_managed.yaml
```

## 6. 快速排查

1. `generate.backend=comfyui requires ... workflow to exist`
- 检查 `generate.comfyui.workflow` 路径。

2. `ComfyUI workflow is UI format`
- workflow 需要 API graph 格式。

3. 长时间无输出
- 检查 `base_url` 连通性、`timeout_sec`、`wait_mode`、`on_timeout`。
