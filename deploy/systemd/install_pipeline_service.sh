#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SERVICE_SRC="${REPO_DIR}/deploy/systemd/dataengine-pipeline.service"
SERVICE_DST="/etc/systemd/system/dataengine-pipeline.service"
ENV_EXAMPLE="${REPO_DIR}/deploy/pipeline/.env.example"
ENV_FILE="${REPO_DIR}/deploy/pipeline/.env"

if [[ ! -f "${SERVICE_SRC}" ]]; then
  echo "service file not found: ${SERVICE_SRC}" >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
fi

sudo cp "${SERVICE_SRC}" "${SERVICE_DST}"
sudo sed -i "s|^WorkingDirectory=.*|WorkingDirectory=${REPO_DIR}|g" "${SERVICE_DST}"
sudo sed -i "s|ExecStart=.*|ExecStart=/usr/bin/docker compose --env-file ${REPO_DIR}/deploy/pipeline/.env -f ${REPO_DIR}/deploy/pipeline/docker-compose.pipeline.yml up --build --remove-orphans|g" "${SERVICE_DST}"
sudo sed -i "s|ExecStop=.*|ExecStop=/usr/bin/docker compose --env-file ${REPO_DIR}/deploy/pipeline/.env -f ${REPO_DIR}/deploy/pipeline/docker-compose.pipeline.yml down|g" "${SERVICE_DST}"

sudo systemctl daemon-reload
sudo systemctl enable --now dataengine-pipeline.service
sudo systemctl status --no-pager dataengine-pipeline.service
