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


echo $PROJECT_ROOT

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
MODELS_DIR="$BASE_DIR/models"

# 5. 给当前脚本执行的宿主权限修改由 docker 创建的/data/comfyui。
if [ ! -w "$PROJECT_ROOT/data/comfyui" ]; then
  echo "⚠️ 正在修复 data/comfyui 权限..."
  sudo chown -R "$USER":"$USER" "$PROJECT_ROOT/data/comfyui"
fi

# mkdir -p \
#   "$ComfyUI_Text_encoders" \
#   "$ComfyUI_Diffuser_models" \
#   "$ComfyUI_VAE" \
#   "$ComfyUI_Model_patches" \
#   "$ComfyUI_Loras" \
#   "$ComfyUI_ControlNet" \
#   "$ComfyUI_Checkpoints" \
#   "$BASE_DIR/comfyui_workflows" \
#   "$BASE_DIR/custom_nodes"

echo "模型将下载到宿主机：$MODELS_DIR （容器内对应 /app/models）"


bash $COMPOSE_DIR/download_models.sh


############################################
# Demo1 Flux1-dev
# ############################################
# # 下载 flux1-dev，量化版本和原始版本 —— 直接进挂载目录
# # workflow:  /home/yan/StudioSpace/DataEngine/data/comfyui/comfyui_workflows/flux_dev.json

# hf download Comfy-Org/flux1-dev \
#   --include "flux1-dev-fp8.safetensors" \
#   --include "flux1-dev.safetensors" \
#   --local-dir "$ComfyUI_Diffuser_models"

# # 下载 CLIP 模型
# hf download comfyanonymous/flux_text_encoders \
#   --include "t5xxl_fp16.safetensors" \
#   --include "clip_l.safetensors" \
#   --local-dir "$ComfyUI_Text_encoders"

# # 下载 VAE 模型
# hf download black-forest-labs/FLUX.1-dev \
#   --include "ae.safetensors" \
#   --local-dir "$ComfyUI_VAE"
# # =========


# ############################################
# # Demo2 QWEN IMAGE MODELS (Comfy-Org)
# ############################################

# # 1) Qwen ControlNet Patch
# hf download Comfy-Org/Qwen-Image-DiffSynth-ControlNets \
#   --include "split_files/model_patches/qwen_image_canny_diffsynth_controlnet.safetensors" \
#   --local-dir "$ComfyUI_Model_patches"
# # https://huggingface.co/Comfy-Org/Qwen-Image-DiffSynth-ControlNets/resolve/main/split_files/model_patches/qwen_image_canny_diffsynth_controlnet.safetensors


# # 2) Qwen VAE
# hf download Comfy-Org/Qwen-Image_ComfyUI \
#   --include "split_files/vae/qwen_image_vae.safetensors" \
#   --local-dir "$ComfyUI_VAE"
# # https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors


# # 3) Qwen Diffusion Model (FP8)
# hf download Comfy-Org/Qwen-Image_ComfyUI \
#   --include "split_files/diffusion_models/qwen_image_fp8_e4m3fn.safetensors" \
#   --local-dir "$ComfyUI_Diffuser_models"
# # https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_fp8_e4m3fn.safetensors


# # 4) Qwen Text Encoder
# hf download Comfy-Org/Qwen-Image_ComfyUI \
#   --include "split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
#   --local-dir "$ComfyUI_Text_encoders"
# # https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors


# hf download lightx2v/Qwen-Image-Lightning \
#   --include "Qwen-Image-Lightning-4steps-V1.0.safetensors" \
#   --local-dir "$ComfyUI_Loras"
# # https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Lightning-4steps-V1.0.safetensors


# ############################################
# # Demo3 Pose - CONTROLNET MODELS
# ############################################

# hf download comfyanonymous/ControlNet-v1-1_fp16_safetensors \
#   --include "control_v11p_sd15_openpose_fp16.safetensors" \
#   --local-dir "$ComfyUI_ControlNet"
# # https://huggingface.co/comfyanonymous/ControlNet-v1-1_fp16_safetensors/resolve/main/control_v11p_sd15_openpose_fp16.safetensors

# hf download stabilityai/sd-vae-ft-mse-original \
#   --include "vae-ft-mse-840000-ema-pruned.safetensors" \
#   --local-dir "$ComfyUI_VAE"
# # https://huggingface.co/stabilityai/sd-vae-ft-mse-original/resolve/main/vae-ft-mse-840000-ema-pruned.safetensors?download=true

# # majicmix realistic v7
# wget "https://civitai.com/api/download/models/176425?type=Model&format=SafeTensor&size=pruned&fp=fp16" \
#   -O "$ComfyUI_Checkpoints/majicmixRealistic_v7.safetensors"

# # japanese style realistic v20
# wget "https://civitai.com/api/download/models/85426?type=Model&format=SafeTensor&size=pruned&fp=fp16" \
#   -O "$ComfyUI_Checkpoints/japaneseStyleRealistic_v20.safetensors"


echo "✅ ComfyUI starting：http://localhost:8188 👍 Now you can feel free to generation anything"
