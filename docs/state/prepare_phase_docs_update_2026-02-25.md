# Prepare Phase Docs Update (2026-02-25)

## Scope
- 仅更新文档，不修改代码逻辑。
- 目标：在入口文档中补齐“运行脚本前的环境准备”阶段，避免新机器直接执行 run scripts 时缺失依赖。

## Changes
- 更新 `README.md`：
  - 新增 `Prepare Phase (before any run scripts)` 小节。
  - 增加 Python 虚拟环境与 `requirements.txt` 安装步骤。
  - 增加 generation 所需系统依赖提示（Docker/Compose、NVIDIA toolkit）。
  - 增加 ComfyUI 启动/健康检查命令。
  - 增加 dataloader 输入路径存在性检查提示。
- 更新 `docs/README_PIPELINE_ZH.md`：
  - 新增“运行前准备（入口）”小节。
  - 将准备阶段指向 `README.md` 的 Prepare Phase，保持主索引文档定位。
  - 调整后续章节编号。

## Result
- 入口文档形成“Prepare -> Run”顺序。
- 新机器启动 generation 前需完成的环境准备可在主入口直接获取。
