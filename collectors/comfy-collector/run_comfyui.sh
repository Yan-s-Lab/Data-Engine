#!/usr/bin/env bash
set -e

# 1. 检查 GPU 可用
if ! docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu20.04 nvidia-smi > /dev/null 2>&1; then
  echo "❌ GPU 容器不可用，请确认已安装 nvidia-container-toolkit 并重启 docker。否则 docker 不能直接使用宿主的 GPU 资源"
  exit 1
fi

# 2. 启动 comfyui 服务
cd "$(dirname "$0")/../infra"
docker compose -f docker-compose.comfyui.yml up -d

echo "✅ ComfyUI 已启动：http://localhost:8188"
