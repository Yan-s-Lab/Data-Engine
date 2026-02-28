# Kernel: Control Generation

## 1. 作用

基于 real anchors manifest + ComfyUI workflow 生成 synthetic，并输出 `synth_manifest.jsonl`。

入口脚本：
- `synth/run_generate.py`

主要实现拆分：
- `synth/comfyui_client.py`：ComfyUI 请求、等待、输出索引
- `synth/comfyui_workflow.py`：workflow 校验与节点注入、anchor 过滤
- `synth/generate_manifest.py`：manifest 配置与产物写入

## 2. Phase 输入输出关系

- 输入：
  - `generate.real_manifest`（来自 dataloader；`guide_type=prompt` 且无 anchor_images 时可省略）
  - `generate.comfyui.workflow`（API prompt graph）
  - prompt/seed/control 配置
- 输出：
  - `<run_dir>/generate/synth_manifest.jsonl`（核心追踪字段）
  - `<run_dir>/generate/report.json`
- 下游关系：
  - `filter` 可读取 `synth_manifest.jsonl`（自动发现）

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
- 当配置 `anchor_image/anchor_images` 时，必须提供非空 `real_manifest`。

4. 执行/超时逻辑
- `non_blocking + max_inflight` 控制并发提交。
- `on_timeout=fail|skip|retry` 与 `timeout_retries` 控制超时策略。

5. 文件名前缀逻辑
- `filename_prefix.template` 可使用 `anchor_image_stem`、`sample_index`、`seed` 等变量。

6. manifest 与输出行为
- `generate.manifest.write_trace_artifacts`（默认 `false`）：
  - 写 `synth_trace_manifest.jsonl`。
- `generate.manifest.guide_type: prompt|image_guided`（默认 `prompt`）：
  - 手动指定本次任务 guide 类型，避免自动推断复杂度。
- `generate.comfyui.output_dir`（默认 `data/comfyui/output`）：
  - generation 只引用 ComfyUI 挂载输出目录中的文件，不再下载/复制图片到 `<run_dir>/generate/images`。
  - 仅接收 ComfyUI `type=output`（通常是 `SaveImage`）产物；`PreviewImage` 等中间 `temp` 输出会被忽略。
- `generate.comfyui.batch_size`：
  - 通过 `node_id/input_key/value` 直接注入 workflow 节点输入，真实控制单个 ComfyUI prompt job 的产图数量。
  - 示例：`node_id=27, input_key=batch_size, value=4`（对应 `EmptySD3LatentImage.inputs.batch_size`）。

核心追踪字段（trace）：
- `synthetic_id`, `synthetic_image_name`, `synthetic_image_path`
- `prompt_text`, `seed`
- `guide_image_id`（prompt-only 为空字符串）
- `guide_type`
- `width`, `height`
- `config_ref`
- `synthetic_image_ids`（同一个 ComfyUI prompt job 的输出 sample_id 数组）

`report.json` 补充字段：
- `synthetic_count`：落盘图片总数（逐图）
- `synthetic_job_count`：ComfyUI prompt running 数（按 `comfy_prompt_id` 去重）

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
