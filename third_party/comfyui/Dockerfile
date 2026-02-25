FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

WORKDIR /app

ARG COMFYUI_REPO=https://github.com/comfyanonymous/ComfyUI.git
ARG COMFYUI_REF=master
RUN git clone --depth=1 --branch "${COMFYUI_REF}" "${COMFYUI_REPO}" .

RUN python -m pip install --upgrade pip && \
    python -m pip install torch==2.3.0+cu121 torchvision==0.18.0+cu121 torchaudio==2.3.0 \
        --index-url https://download.pytorch.org/whl/cu121 && \
    python -m pip install -r requirements.txt

RUN mkdir -p /app/models /app/output /app/custom_nodes /app/user/default/workflows

EXPOSE 8188

ENV COMFYUI_PORT=8188 \
    COMFYUI_EXTRA_ARGS="--disable-auto-launch"

CMD ["bash", "-lc", "python main.py --listen 0.0.0.0 --port ${COMFYUI_PORT} ${COMFYUI_EXTRA_ARGS}"]
