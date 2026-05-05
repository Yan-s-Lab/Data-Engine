# Prepare Phase Conda Update (2026-02-25)

## Scope
- 仅更新文档，不修改代码逻辑。
- 目标：将环境准备步骤与当前本地实践对齐为 `conda + pip`。

## Changes
- 更新 `README.md` 的 `Prepare Phase (before any run scripts)`：
  - 将 Python 环境主路径改为 `conda create/conda activate + pip install`。
  - 保留 `venv` 作为可选 fallback。

## Result
- 入口环境准备与当前团队本地使用方式一致。
