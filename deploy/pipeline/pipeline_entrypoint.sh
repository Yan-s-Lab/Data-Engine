#!/usr/bin/env bash
set -euo pipefail

cd /workspace

CONFIG_PATH="${PIPELINE_CONFIG:-configs/examples/dataloader_norm_test.yaml}"
PY_BIN="${PIPELINE_PYTHON_BIN:-python}"
RESUME_FLAG="${PIPELINE_RESUME:-true}"
LOG_DIR="${PIPELINE_LOG_DIR:-/workspace/artifacts/logs}"
LOG_FILE="${PIPELINE_LOG_FILE:-${LOG_DIR}/managed_pipeline.log}"

mkdir -p "${LOG_DIR}"

echo "[entrypoint] config=${CONFIG_PATH} resume=${RESUME_FLAG} log=${LOG_FILE}" | tee -a "${LOG_FILE}"

exec ${PY_BIN} pipelines/run_managed_pipeline.py \
  --config "${CONFIG_PATH}" \
  --resume "${RESUME_FLAG}" >>"${LOG_FILE}" 2>&1
