#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ✅ 先算项目根目录（假设 run_comfyui.sh 在 scripts/ 或类似位置）
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 1. 检查 GPU 可用（保持不变）
if ! docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi > /dev/null 2>&1; then
  echo "❌ GPU 容器不可用，请确认已安装 nvidia-container-toolkit 并重启 docker。"
  echo " Please flow up this command line to install 
    sudo apt install nvidia-container-toolkit
    sudo systemctl restart docker
    重新验证
    docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi
    "
  exit 1
fi

# 2. 启动 comfyui 服务 —— ✅ 改为用 infra/docker-compose.yml 里的 comfyui service
cd "$PROJECT_ROOT/infra"
docker compose -f docker-compose.yml up -d comfyui

# 3. 统一一个宿主机模型目录（跟 compose 里的 volume 对应）
BASE_DIR="$PROJECT_ROOT/data/comfyui"
MODELS_DIR="$BASE_DIR/models"

# flux1-dev需要的几个文件
ComfyUI_Diffuser_models="$MODELS_DIR/diffusion_models"
ComfyUI_Text_encoders="$MODELS_DIR/text_encoders"
ComfyUI_VAE="$MODELS_DIR/vae"

# 给当前脚本执行的宿主权限修改由 docker 创建的/data/comfyui。
if [ ! -w "$PROJECT_ROOT/data/comfyui" ]; then
  echo "⚠️ 正在修复 data/comfyui 权限..."
  sudo chown -R "$USER":"$USER" "$PROJECT_ROOT/data/comfyui"
fi

# 创建文件目录
mkdir -p "$MODELS_DIR/text_encoders"
mkdir -p "$MODELS_DIR/diffusion_models"
mkdir -p "$MODELS_DIR/vae"

# 给 workflow 挂载创造宿主文件目录
mkdir -p "$BASE_DIR/comfyui_workflows" # 对应了 docker 下的/app/user/default/workflows
mkdir -p "$BASE_DIR/custom_nodes"      # 对应 /app/custom_nodes，顺便补上

echo "模型将下载到宿主机：$MODELS_DIR （容器内对应 /app/models）"

# 下载 flux1-dev，量化版本和原始版本 —— 直接进挂载目录
hf download Comfy-Org/flux1-dev \
  --include "flux1-dev-fp8.safetensors" \
  --include "flux1-dev.safetensors" \
  --local-dir "$ComfyUI_Diffuser_models"

# 下载 CLIP 模型
hf download comfyanonymous/flux_text_encoders \
  --include "t5xxl_fp16.safetensors" \
  --include "clip_l.safetensors" \
  --local-dir "$ComfyUI_Text_encoders"

# 下载 VAE 模型
hf download black-forest-labs/FLUX.1-dev \
  --include "ae.safetensors" \
  --local-dir "$ComfyUI_VAE"

echo "✅ ComfyUI starting：http://localhost:8188 👍 Now you can feel free to generation anything"
