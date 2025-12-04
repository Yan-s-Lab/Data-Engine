#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# ✅ 先算项目根目录（假设 run_comfyui.sh 在 scripts/ 或类似位置）
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 1. GPU 检查
if ! docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi > /dev/null 2>&1; then
  echo "❌ GPU 容器不可用，请确认已安装 nvidia-container-toolkit 并重启 docker。"
  echo "   sudo apt install nvidia-container-toolkit"
  echo "   sudo systemctl restart docker"
  echo "   docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi"
  exit 1
fi

# 2. 启动 comfyui 服务，如果旧的 comfyui 容器存在，先优雅关闭再删掉（不影响其它容器）
COMPOSE_DIR="$PROJECT_ROOT/infra/ComfyUI"
COMPOSE_FILE="$COMPOSE_DIR/docker-compose.comfyui.yml"
SERVICE_NAME="comfyui"          # docker compose 里的 service 名
CONTAINER_NAME="comfyui-service" # docker-compose.comfyui.yml 里 container_name 写的这个

cd "$COMPOSE_DIR"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
  echo "♻️ 检测到已有容器 ${CONTAINER_NAME}，正在停止并移除..."
  docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
  docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi
# 也可以顺手把同一个 compose 项目的“僵尸容器”清一下（只影响这个 yml 定义的服务）
docker compose -f "$COMPOSE_FILE" down >/dev/null 2>&1 || true

# 3. 启动 comfyui 服务（这时不会再有 name 冲突）
echo "🚀 启动 ComfyUI 容器..."
docker compose -f "$COMPOSE_FILE" up -d "$SERVICE_NAME"


# 4. 统一一个宿主机模型目录（跟 compose 里的 volume 对应）
BASE_DIR="$PROJECT_ROOT/data/comfyui" 

# 5. 给当前脚本执行的宿主权限修改由 docker 创建的/data/comfyui。
if [ ! -w "$PROJECT_ROOT/data/comfyui" ]; then
  echo "⚠️ 正在修复 data/comfyui 权限..."
  sudo chown -R "$USER":"$USER" "$PROJECT_ROOT/data/comfyui"
fi


echo "模型将下载到宿主机：$BASE_DIR/models （容器内对应 /app/models）"


# 下载默认的 demo workflow models dependences
bash $COMPOSE_DIR/download_models.sh

echo "✅ ComfyUI starting：http://localhost:8188 👍 Now you can feel free to generation anything"
