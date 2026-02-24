
# Data Flow (Current, Methods-Aligned)

本文档只描述**当前仓库可运行的数据流**，并对齐 `.temp/methods.tex` 的阶段定义。

## 1. 论文方法到当前实现的映射

`methods.tex` 的 5 段式方法：
1. Task + Real Anchors
2. Synthetic-First Generation
3. Real-Calibrated Cascaded Filtering
4. Annotation / Label Refinement
5. Training-Aware Feedback Loop

当前仓库映射：
1. `dataloader`：产出 real anchors manifest
2. `generate`：`local_stub` 或 `comfyui` 生成 synthetic
3. `filter`：`stub | pcs_clip | staged_clip | compose`（含 phase1 semantic routing）
4. `label`：Label Studio push/pull CLI 已有，但未并入默认单轮 pipeline
5. `train -> eval`：当前为 stub 训练评估，产出 `policy_feedback.json`

## 2. 当前默认可运行闭环

默认单机闭环：

`dataloader -> generate -> filter -> train -> eval`

入口：

`pipelines/run_yaml_pipeline.py`

说明：
- 该闭环是**方法学骨架可运行版**（MVP），并非完整算法实现。
- `eval` 输出策略建议，但尚未自动回写配置形成全自动多轮优化。

## 3. 两条已落地执行路径

1. M1 最小本地回路（验证 artifact 合同）  
`filter -> train -> eval`  
入口：`pipelines/filter_train_eval_round.py`

2. M2 单机 YAML 闭环（默认推荐）  
`dataloader -> generate -> filter -> train -> eval`  
入口：`pipelines/run_yaml_pipeline.py`

## 4. 文档边界（防止状态漂移）

- **事实状态**：`docs/state/data_engine_state.md`
- **阶段运行手册**：`docs/README_PIPELINE_ZH.md`
- **目标设计（aspirational）**：`docs/design/*.md`

历史性的 service 命名流程（如 `mine-service`、`YOLOv11n-seg` 等）不再作为“当前实现事实”来源，应只保留在设计讨论文档中。
