# ComfyUI Docker Python Compatibility Fix (2026-02-25)

## Scope
- 修复 ComfyUI docker build 在依赖安装阶段因 Python 3.8 与新依赖约束不兼容导致失败的问题。

## Root Cause
- `third_party/comfyui/Dockerfile` 使用 `nvidia/cuda:12.1.1-runtime-ubuntu20.04`。
- 该基础镜像通过 apt 安装到的 `python3` 为 3.8。
- 构建阶段安装 PyTorch 2.3.0+cu121 及其依赖时拉取 `typing-extensions>=4.15`，要求 Python >= 3.9，导致失败。

## Changes
- 更新基础镜像：
  - `nvidia/cuda:12.1.1-runtime-ubuntu20.04` -> `nvidia/cuda:12.1.1-runtime-ubuntu22.04`
- 调整 pip 调用：
  - `pip ...` -> `python -m pip ...`（避免 PATH/多 pip 二义性）

## Result
- ComfyUI 镜像构建环境切到 Python 3.10 基线，可满足当前依赖约束。
