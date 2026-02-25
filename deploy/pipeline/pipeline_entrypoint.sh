#!/usr/bin/env bash
set -euo pipefail

cd /workspace

PY_BIN="${PIPELINE_PYTHON_BIN:-python}"
RESUME_FLAG="${PIPELINE_RESUME:-true}"
LOG_DIR="${PIPELINE_LOG_DIR:-/workspace/artifacts/logs}"
LOG_FILE="${PIPELINE_LOG_FILE:-${LOG_DIR}/managed_pipeline.log}"
CONTINUE_ON_ERROR="${PIPELINE_CONTINUE_ON_ERROR:-false}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

DEFAULT_SINGLE_CONFIG="configs/examples/dataloader_norm_test.yaml"
CONFIG_PATH="${PIPELINE_CONFIG:-${DEFAULT_SINGLE_CONFIG}}"
CONFIGS_CSV="${PIPELINE_CONFIGS:-}"
CONFIG_LIST_FILE="${PIPELINE_CONFIG_LIST_FILE:-}"
SERIAL_PLAN="${PIPELINE_SERIAL_PLAN:-}"

mkdir -p "${LOG_DIR}"

to_bool() {
  local value="${1:-false}"
  value="$(echo "${value}" | tr '[:upper:]' '[:lower:]')"
  [[ "${value}" == "1" || "${value}" == "true" || "${value}" == "yes" || "${value}" == "y" ]]
}

trim() {
  local s="${1:-}"
  s="${s#${s%%[![:space:]]*}}"
  s="${s%${s##*[![:space:]]}}"
  echo "${s}"
}

declare -a CONFIG_QUEUE=()

if [[ -n "${SERIAL_PLAN}" ]]; then
  echo "[entrypoint] serial plan mode: plan=${SERIAL_PLAN}" | tee -a "${LOG_FILE}"
  exec ${PY_BIN} pipelines/run_serial_plan.py \
    --plan "${SERIAL_PLAN}" \
    --python-bin "${PY_BIN}" \
    --resume "${RESUME_FLAG}" \
    --log-dir "${LOG_DIR}" \
    --log-file "${LOG_FILE}" \
    --continue-on-error "${CONTINUE_ON_ERROR}"
elif [[ -n "${CONFIG_LIST_FILE}" ]]; then
  if [[ ! -f "${CONFIG_LIST_FILE}" ]]; then
    echo "[entrypoint] ERROR: PIPELINE_CONFIG_LIST_FILE not found: ${CONFIG_LIST_FILE}" | tee -a "${LOG_FILE}"
    exit 2
  fi
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="$(trim "${line}")"
    [[ -z "${line}" || "${line}" == \#* ]] && continue
    CONFIG_QUEUE+=("${line}")
  done < "${CONFIG_LIST_FILE}"
elif [[ -n "${CONFIGS_CSV}" ]]; then
  IFS=',' read -r -a RAW_CONFIGS <<< "${CONFIGS_CSV}"
  for item in "${RAW_CONFIGS[@]}"; do
    item="$(trim "${item}")"
    [[ -z "${item}" ]] && continue
    CONFIG_QUEUE+=("${item}")
  done
else
  CONFIG_QUEUE+=("${CONFIG_PATH}")
fi

if [[ "${#CONFIG_QUEUE[@]}" -eq 0 ]]; then
  echo "[entrypoint] ERROR: no pipeline config resolved" | tee -a "${LOG_FILE}"
  exit 2
fi

echo "[entrypoint] queue_size=${#CONFIG_QUEUE[@]} resume=${RESUME_FLAG} continue_on_error=${CONTINUE_ON_ERROR}" | tee -a "${LOG_FILE}"
echo "[entrypoint] queue=${CONFIG_QUEUE[*]}" | tee -a "${LOG_FILE}"

fail_count=0

for index in "${!CONFIG_QUEUE[@]}"; do
  cfg="${CONFIG_QUEUE[$index]}"
  cfg_basename="$(basename "${cfg}")"
  job_name="${cfg_basename%.*}"
  job_log="${LOG_DIR}/${job_name}_${TIMESTAMP}.log"

  echo "[entrypoint] start job=$((index + 1))/${#CONFIG_QUEUE[@]} config=${cfg} log=${job_log}" | tee -a "${LOG_FILE}"

  if ${PY_BIN} pipelines/run_managed_pipeline.py --config "${cfg}" --resume "${RESUME_FLAG}" >>"${job_log}" 2>&1; then
    echo "[entrypoint] done config=${cfg}" | tee -a "${LOG_FILE}"
  else
    fail_count=$((fail_count + 1))
    echo "[entrypoint] failed config=${cfg} fail_count=${fail_count}" | tee -a "${LOG_FILE}"
    if ! to_bool "${CONTINUE_ON_ERROR}"; then
      echo "[entrypoint] exit on first failure" | tee -a "${LOG_FILE}"
      exit 1
    fi
  fi
done

if [[ "${fail_count}" -gt 0 ]]; then
  echo "[entrypoint] completed with failures: ${fail_count}" | tee -a "${LOG_FILE}"
  exit 1
fi

echo "[entrypoint] all jobs completed successfully" | tee -a "${LOG_FILE}"
