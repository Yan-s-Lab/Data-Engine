#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/models.yaml"
BASE_DIR="${PROJECT_ROOT}/data/comfyui/models"

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "missing model config: ${CONFIG_FILE}" >&2
  exit 1
fi

command -v yq >/dev/null 2>&1 || { echo "missing dependency: yq" >&2; exit 1; }

if ! command -v hf >/dev/null 2>&1; then
  echo "missing dependency: hf (huggingface-cli). install: pip install -U huggingface_hub[hf_transfer]" >&2
  exit 1
fi

mkdir -p "${BASE_DIR}"
MODEL_COUNT="$(yq '.models | length' "${CONFIG_FILE}")"

echo "models to check: ${MODEL_COUNT}"
for i in $(seq 0 $((MODEL_COUNT - 1))); do
  name="$(yq -r ".models[${i}].name" "${CONFIG_FILE}")"
  source="$(yq -r ".models[${i}].source" "${CONFIG_FILE}")"
  dest="$(yq -r ".models[${i}].dest" "${CONFIG_FILE}")"
  target_dir="${BASE_DIR}/${dest}"
  mkdir -p "${target_dir}"

  echo "--- ${name} (${source}) -> ${target_dir}"

  if [[ "${source}" == "huggingface" ]]; then
    repo="$(yq -r ".models[${i}].repo" "${CONFIG_FILE}")"
    while IFS= read -r file; do
      [[ -n "${file}" ]] || continue
      target_file="${target_dir}/$(basename "${file}")"
      if [[ -f "${target_file}" ]]; then
        echo "skip existing: ${target_file}"
        continue
      fi
      echo "download hf: ${repo}/${file}"
      hf download "${repo}" --include "${file}" --local-dir "${target_dir}"
    done < <(yq -r ".models[${i}].files[]" "${CONFIG_FILE}")

  elif [[ "${source}" == "civitai" ]]; then
    command -v curl >/dev/null 2>&1 || { echo "missing dependency: curl" >&2; exit 1; }
    url="$(yq -r ".models[${i}].url" "${CONFIG_FILE}")"
    filename="$(yq -r ".models[${i}].filename" "${CONFIG_FILE}")"
    target_file="${target_dir}/${filename}"
    if [[ -f "${target_file}" ]]; then
      echo "skip existing: ${target_file}"
      continue
    fi
    echo "download civitai: ${filename}"
    curl -fL "${url}" -o "${target_file}"

  else
    echo "unsupported source for model ${name}: ${source}" >&2
    exit 1
  fi

done

echo "model check/download finished"
