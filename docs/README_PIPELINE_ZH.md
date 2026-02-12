# DataEngine 傻瓜式 Pipeline 手册

这份手册只做一件事: 让你最快跑通闭环。

默认闭环:
`dataloader -> generate -> filter -> train -> eval`

入口脚本:
`pipelines/run_yaml_pipeline.py`

---

## 1. 先决条件

1. 你在项目根目录:
```bash
cd /home/yan/StudioSpace/DataEngine
```
2. Python 环境可用（`python --version` 可执行）。
3. 真实图片目录存在（默认示例用 `data/raw/collection_1`）。

---

## 2. 最快跑通（不依赖 ComfyUI）

这是本地 stub 版本，用来验证流程是否通。

运行:
```bash
python pipelines/run_yaml_pipeline.py \
  --config configs/examples/min_single_node_closed_loop.yaml
```

成功标志:
- `artifacts/runs/m2_single_node_closed_loop_demo/pipeline/summary.json` 中 `status` 为 `ok`

核心输出:
- `artifacts/runs/m2_single_node_closed_loop_demo/generate/mixed_manifest.jsonl`
- `artifacts/runs/m2_single_node_closed_loop_demo/filter/splits/accept.jsonl`
- `artifacts/runs/m2_single_node_closed_loop_demo/train/model_stub.json`
- `artifacts/runs/m2_single_node_closed_loop_demo/eval/metrics.json`
- `artifacts/runs/m2_single_node_closed_loop_demo/eval/policy_feedback.json`

---

## 3. 真实生成版（接 ComfyUI）

### 3.1 启动 ComfyUI 服务
在 ComfyUI 目录执行:
```bash
python main.py --listen 0.0.0.0 --port 8188 --highvram
```

### 3.2 准备配置
使用这个配置文件:
- `configs/examples/min_single_node_closed_loop_comfyui.yaml`

至少确认这两个字段:
- `generate.comfyui.base_url`（默认 `http://127.0.0.1:8188`）
- `generate.comfyui.workflow`（你的 API workflow json 路径）

### 3.3 运行闭环
```bash
python pipelines/run_yaml_pipeline.py \
  --config configs/examples/min_single_node_closed_loop_comfyui.yaml
```

成功标志:
- `artifacts/runs/m2_single_node_closed_loop_comfyui_demo/pipeline/summary.json` 中 `status` 为 `ok`

---

## 4. 常改配置项（最小集合）

### 4.1 dataloader
- `dataloader.real_dir`: 真实数据目录
- `dataloader.max_samples`: 限制本轮真实样本数（快速实验建议先小数）

### 4.2 generate
- `generate.backend`: `local_stub` 或 `comfyui`
- `generate.synth_per_real`: 每张真实图生成几张合成图
- `generate.max_synth_samples`: 本轮最多生成多少合成图
- `generate.seed_base`: 基础随机种子

ComfyUI 专属:
- `generate.comfyui.wait_mode`: `history` 或 `websocket`
- `generate.comfyui.client_id`: 可固定，便于追踪
- `generate.comfyui.extra_data`: 透传到 `/prompt`（比如 API key）
- `generate.comfyui.seed_node_id`: workflow 中要注入 seed 的节点 id
- `generate.comfyui.seed_input_key`: 一般是 `seed`

### 4.3 filter/train/eval
- `filter.accept_threshold`
- `train.max_train_samples`
- `eval.target_map50`

---

## 5. 一轮闭环后该看什么

1. 看效果:
- `.../eval/metrics.json`

2. 看下一轮策略建议:
- `.../eval/policy_feedback.json`

3. 看数据筛选质量:
- `.../filter/report.json`
- `.../filter/splits/accept.jsonl`

---

## 6. 最常见错误排查

1. 报 `missing real manifest`
- 通常是 `dataloader` 阶段没产出，先看 `.../dataloader/report.json`

2. 报 `generate.backend=comfyui requires ... workflow to exist`
- `generate.comfyui.workflow` 路径错误

3. ComfyUI 一直无结果
- 确认 ComfyUI 服务已启动、端口正确
- 先把 `wait_mode` 设为 `history`
- 检查 workflow 是否是 API 导出格式（不是 UI 原始格式）

4. `websocket` 模式报错
- 当前环境缺少可用 websocket sync 客户端或连接失败
- 先用 `wait_mode: history` 验证跑通

---

## 7. 推荐日常命令（复制即用）

本地快速回归:
```bash
python pipelines/run_yaml_pipeline.py \
  --config configs/examples/min_single_node_closed_loop.yaml
```

ComfyUI 真实生成回归:
```bash
python pipelines/run_yaml_pipeline.py \
  --config configs/examples/min_single_node_closed_loop_comfyui.yaml
```
