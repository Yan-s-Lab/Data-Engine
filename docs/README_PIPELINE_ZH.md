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

### 3.1 启动 ComfyUI 服务（先检查，不通再启动）
项目内置了 ComfyUI 第三方子系统编排文件，统一入口:
```bash
./third_party/comfyui/comfyui_ctl.sh ensure
```

说明:
- `ensure`: 先检查 `http://127.0.0.1:8188/system_stats`，可用则直接复用；不可用则 `docker compose up -d --build`
- `status`: `./third_party/comfyui/comfyui_ctl.sh status`
- `logs`: `./third_party/comfyui/comfyui_ctl.sh logs`
- 兼容旧入口（含 GPU 检查）:
```bash
./third_party/comfyui/run_comfyui.sh
```
- 模型/权重下载（可单独执行）:
```bash
./third_party/comfyui/download_models.sh
```
- `run_comfyui.sh` 默认会执行模型检查与下载；如需跳过:
```bash
DOWNLOAD_MODELS=0 ./third_party/comfyui/run_comfyui.sh
```
- 如果需要自定义参数，先复制环境模板:
```bash
cp third_party/comfyui/.env.example third_party/comfyui/.env
```

### 3.2 准备配置
使用这个配置文件:
- `configs/examples/min_single_node_closed_loop_comfyui.yaml`

至少确认这两个字段:
- `generate.comfyui.base_url`（默认 `http://127.0.0.1:8188`）
- `generate.comfyui.workflow`（你的 **API prompt graph** 路径，不是 UI workflow 导出）

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
- `generate.comfyui.non_blocking`: 是否启用“多 prompt 并发提交 + 轮询 history”的非阻塞模式（建议配 `history`）
- `generate.comfyui.max_inflight`: 非阻塞模式下最多并发中的 prompt 数
- `generate.comfyui.client_id`: 可固定，便于追踪
- `generate.comfyui.extra_data`: 透传到 `/prompt`（比如 API key）
- `generate.comfyui.seed_node_id`: workflow 中要注入 seed 的节点 id
- `generate.comfyui.seed_input_key`: 一般是 `seed`

### 4.3 filter/train/eval
- `filter.mode`: `stub` / `pcs_clip` / `staged_clip`
- `filter.keep_real_always`（`staged_clip` 默认 `true`，真实样本强制保留）
- `filter.accept_threshold`
- `filter.uncertain_low` / `filter.uncertain_high`
- `filter.clip_model_id`（`pcs_clip` 模式）
- `filter.pcs.repeats`（扰动次数）
- `filter.pcs.grid_rows` / `filter.pcs.grid_cols`（像素块网格）
- `filter.pcs.swap_ratio`（每次扰动打乱比例）
- `filter.pcs.synthetic_only`（只对 synthetic 跑 PCS）
- `filter.score.*`（`staged_clip` 的加权融合参数）
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
- 先执行 `./third_party/comfyui/comfyui_ctl.sh ensure`
- 先把 `wait_mode` 设为 `history`
- 检查 `generate.comfyui.workflow` 是否是 API prompt graph 格式（不是 UI 原始 workflow）

4. 想完全用配置/API，不想走 UI 导出
- 可以直接在配置里使用 `generate.comfyui.prompt_graph`（内联 API graph）
- 或者在 `generate.comfyui.workflow` 指向手写/程序生成的 API graph json/yaml
- 可选用 `generate.comfyui.prompt.*` 把文本 prompt 注入指定节点
- 可选用 `generate.comfyui.anchor_image.*` 把每个 real-anchor 图片上传到 ComfyUI，并注入到指定图像输入节点
- 若 workflow 里有多个控制图入口（如 pose+canny），可用 `generate.comfyui.anchor_images[]` 一次注入多个节点输入

5. `websocket` 模式报错
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

PCS-CLIP 过滤回归（像素块扰动 + CLIP 相似度）:
```bash
python pipelines/run_yaml_pipeline.py \
  --config configs/examples/min_single_node_closed_loop_pcs_clip.yaml
```

分层过滤 smoke（`clip_embed_cache -> prompt -> consistency -> dedup -> quality`）:
```bash
python pipelines/run_yaml_pipeline.py \
  --config configs/examples/min_single_node_closed_loop_staged_clip.yaml
```

可组合过滤 smoke（按 `stages + policy` 组合 Filter）:
```bash
python pipelines/run_yaml_pipeline.py \
  --config configs/examples/min_single_node_closed_loop_compose_clip.yaml
```

`staged_clip` 产出的 `filter/filter_scores.jsonl` 行格式示例:
```json
{
  "image_id": "...",
  "s_prompt_margin": 0.18,
  "s_multicrop_consistency": 0.86,
  "ood_md2": 24.1,
  "dup_sim": 0.997,
  "blur_score": 12.4,
  "final_score": 0.68,
  "keep": false,
  "decision_basis": "tri_gate"
}
```

单控制任务（只跑 generate）:
```bash
python synth/run_generate.py --config configs/examples/comfyui_generate_from_norm_yk001_prompt_pose.yaml
python synth/run_generate.py --config configs/examples/comfyui_generate_from_norm_yk001_prompt_canny.yaml
python synth/run_generate.py --config configs/examples/comfyui_generate_from_norm_yk001_prompt_style.yaml
```
