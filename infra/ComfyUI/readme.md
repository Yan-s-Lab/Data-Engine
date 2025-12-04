
# ComfyUI Service Integration (Infrastructure Layer)

This document explains how to **install ComfyUI**, **expose it as a remote-accessible service**, and **handle common dependency issues** when running inside the Data-Engine infrastructure.

---

## 1. Installation Guide (Linux)

You may refer to the official documentation first:
🔗 **ComfyUI Linux Installation Manual**
[https://docs.comfy.org/installation/manual_install#linux](https://docs.comfy.org/installation/manual_install#linux)

Below is a concise and reproducible setup script:

```bash
# Create environment
conda create -n comfyenv
conda activate comfyenv

# Clone repo
git clone git@github.com:comfyanonymous/ComfyUI.git

# Install PyTorch (CUDA 12.1)
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia

# (Optional alternative)
# pip install torch==2.3.0+cu121 torchvision==0.18.0+cu121 torchaudio==2.3.0 \
#   --index-url https://download.pytorch.org/whl/cu121

# Fix potential MKL / Intel OpenMP issues that break PyTorch runtime
# (avoids: libtorch_cpu.so: undefined symbol: iJIT_NotifyEvent)
conda install "mkl<=2024.0.0" "intel-openmp<=2024.0.0" -c defaults -y

# Install ComfyUI dependencies
cd ComfyUI
pip install -r requirements.txt
```

---

## 2. Expose ComfyUI for Remote Access

By default, ComfyUI binds to **127.0.0.1**, meaning it cannot be accessed by other machines.

To expose the service for **LAN / remote access**, run:

```bash
python main.py --listen 0.0.0.0 --port 8188
```

* `0.0.0.0` → accepts requests from all network interfaces
* Remote access example:
  `http://<your-server-ip>:8188/`

This allows the Data-Engine or other collectors to call this ComfyUI node as a **standalone model-serving backend**.

---

## 3. Common PyTorch Issue: `iJIT_NotifyEvent` Error

If you see:

```
torch/lib/libtorch_cpu.so: undefined symbol: iJIT_NotifyEvent
```

This typically happens when **Conda auto-updates MKL/Intel OpenMP** to a version incompatible with your PyTorch build.

Fix (verified):

```bash
conda install "mkl<=2024.0.0" "intel-openmp<=2024.0.0" -c defaults -y
```

Reference:
[https://github.com/pytorch/pytorch/issues/123097#issuecomment-2055236551](https://github.com/pytorch/pytorch/issues/123097#issuecomment-2055236551)

---

## 4. Customized T2I Pipeline (Work in Progress)

A dedicated section will be added soon to describe:

* how to plug custom Stable Diffusion / FLUX pipelines
* how Data-Engine interacts with ComfyUI as a **third-party generative service**
* how to orchestrate multi-node ComfyUI models
* how to unify output directories for collectors

*Coming soon…*

---

## 5. Notes for Data-Engine Integration

When used within the Data-Engine micro-services:

* Treat ComfyUI as a **third-party model service**, not part of collectors，just as a third part component(Data engine will handel conncetor jobs)
* Collectors (e.g., `synthetic-service`, `comfy-collector`) should call the **exposed HTTP API**
* ComfyUI should not live inside the `services/` folder; it is infrastructure
* Volume mapping for models should be unified in `docker-compose.comfyui.yml`

This separation keeps the architecture clean:

```
infra/
  └── ComfyUI/   ← model backend (third-party)
collectors/
  └── comfy-collector/ ← our pipeline logic
services/
  └── collection-gateway/ 
```

