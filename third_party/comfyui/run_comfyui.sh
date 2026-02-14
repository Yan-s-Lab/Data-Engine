#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOWNLOAD_MODELS="${DOWNLOAD_MODELS:-1}"

# 1) GPU check
if ! docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu20.04 nvidia-smi >/dev/null 2>&1; then
  echo "GPU container unavailable. Install nvidia-container-toolkit and restart docker." >&2
  exit 1
fi

# 2) check -> start
"${SCRIPT_DIR}/comfyui_ctl.sh" ensure

# 3) optional model bootstrap
if [[ "${DOWNLOAD_MODELS}" == "1" ]]; then
  "${SCRIPT_DIR}/download_models.sh"
else
  echo "skip model download: DOWNLOAD_MODELS=${DOWNLOAD_MODELS}"
fi
