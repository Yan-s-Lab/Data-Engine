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

command -v python3 >/dev/null 2>&1 || { echo "missing dependency: python3" >&2; exit 1; }
python3 -c 'import yaml' >/dev/null 2>&1 || {
  echo "missing dependency: pyyaml. install from requirements.txt or pip install pyyaml" >&2
  exit 1
}

if ! command -v hf >/dev/null 2>&1; then
  echo "missing dependency: hf (huggingface-cli). install: pip install -U huggingface_hub[hf_transfer]" >&2
  exit 1
fi

mkdir -p "${BASE_DIR}"
MODEL_COUNT="$(python3 - "${CONFIG_FILE}" <<'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}
models = data.get("models", [])
print(len(models))
PY
)"

echo "models to check: ${MODEL_COUNT}"
while IFS=$'\t' read -r source name dest repo file url filename; do
  target_dir="${BASE_DIR}/${dest}"
  mkdir -p "${target_dir}"

  echo "--- ${name} (${source}) -> ${target_dir}"

  if [[ "${source}" == "huggingface" ]]; then
    target_file="${target_dir}/$(basename "${file}")"
    if [[ -f "${target_file}" ]]; then
      echo "skip existing: ${target_file}"
      continue
    fi
    echo "download hf: ${repo}/${file}"
    hf download "${repo}" --include "${file}" --local-dir "${target_dir}"

  elif [[ "${source}" == "civitai" ]]; then
    command -v curl >/dev/null 2>&1 || { echo "missing dependency: curl" >&2; exit 1; }
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
done < <(python3 - "${CONFIG_FILE}" <<'PY'
import sys
import yaml

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

for model in data.get("models", []):
    source = model.get("source", "")
    name = model.get("name", "")
    dest = model.get("dest", "")
    if source == "huggingface":
        repo = model.get("repo", "")
        for file in model.get("files", []) or []:
            print("\t".join([source, name, dest, repo, file, "", ""]))
    elif source == "civitai":
        url = model.get("url", "")
        filename = model.get("filename", "")
        print("\t".join([source, name, dest, "", "", url, filename]))
    else:
        print("\t".join([source, name, dest, "", "", "", ""]))
PY
)

echo "model check/download finished"
