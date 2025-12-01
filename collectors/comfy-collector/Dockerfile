# 基于 CUDA 12.1 + Ubuntu 20.04 的运行时镜像
FROM nvidia/cuda:12.1.1-runtime-ubuntu20.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 基础依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 统一用 python 指向 python3
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

WORKDIR /app

# 克隆 ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git .

# 安装 PyTorch（CUDA 12.1 版）+ ComfyUI 依赖
RUN pip install --upgrade pip && \
    pip install torch==2.3.0+cu121 torchvision==0.18.0+cu121 torchaudio==2.3.0 \
        --index-url https://download.pytorch.org/whl/cu121 && \
    pip install -r requirements.txt

# 预留挂载点
RUN mkdir -p /app/models /app/output /app/custom_nodes

EXPOSE 8188

ENV COMFYUI_PORT=8188 \
    COMFYUI_EXTRA_ARGS="--disable-auto-launch"

CMD ["bash", "-lc", "python main.py --listen 0.0.0.0 --port ${COMFYUI_PORT} ${COMFYUI_EXTRA_ARGS}"]
