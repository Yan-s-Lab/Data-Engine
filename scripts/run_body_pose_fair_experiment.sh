#!/usr/bin/env bash
set -euo pipefail

PLAN="${1:-configs/coco_pose_2017__expansion/pipeline_fair_pose_ablation.yaml}"
PYTHON_BIN="${PYTHON_BIN:-python}"
RESUME="${RESUME:-true}"
LOG_DIR="${LOG_DIR:-artifacts/logs/body_pose_fair_experiment}"

exec "${PYTHON_BIN}" pipelines/run_serial_plan.py \
  --plan "${PLAN}" \
  --python-bin "${PYTHON_BIN}" \
  --resume "${RESUME}" \
  --log-dir "${LOG_DIR}" \
  --log-file "${LOG_DIR}/serial_plan.log"
