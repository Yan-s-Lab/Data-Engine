#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.label-studio.yml"
ENV_FILE="${SCRIPT_DIR}/.env"

compose() {
  if [[ -f "${ENV_FILE}" ]]; then
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
  else
    docker compose -f "${COMPOSE_FILE}" "$@"
  fi
}

base_url() {
  local host_port="8080"
  if [[ -f "${ENV_FILE}" ]]; then
    host_port="$(grep -E '^LABEL_STUDIO_PORT=' "${ENV_FILE}" | tail -n 1 | cut -d'=' -f2- || true)"
    host_port="${host_port:-8080}"
  fi
  printf 'http://127.0.0.1:%s' "${host_port}"
}

container_name() {
  local name="label-studio-service"
  if [[ -f "${ENV_FILE}" ]]; then
    name="$(grep -E '^LABEL_STUDIO_CONTAINER_NAME=' "${ENV_FILE}" | tail -n 1 | cut -d'=' -f2- || true)"
    name="${name:-label-studio-service}"
  fi
  printf '%s' "${name}"
}

check_service() {
  local url
  url="$(base_url)"
  curl -fsS "${url}/api/health" >/dev/null 2>&1 || curl -fsS "${url}/health" >/dev/null 2>&1
}

wait_for_service() {
  local attempts="${1:-20}"
  local sleep_sec="${2:-3}"
  local i
  for ((i=1; i<=attempts; i++)); do
    if check_service; then
      return 0
    fi
    sleep "${sleep_sec}"
  done
  return 1
}

cmd="${1:-ensure}"

case "${cmd}" in
  status)
    compose ps
    docker ps --filter "name=$(container_name)" --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}'
    ;;
  check)
    if wait_for_service "${LABEL_STUDIO_CHECK_RETRIES:-20}" "${LABEL_STUDIO_CHECK_INTERVAL_SEC:-3}"; then
      echo "label-studio: healthy at $(base_url)"
    else
      echo "label-studio: unavailable at $(base_url)" >&2
      exit 1
    fi
    ;;
  start)
    compose up -d
    compose ps
    ;;
  ensure)
    if check_service; then
      echo "label-studio: already healthy at $(base_url)"
      compose ps
      docker ps --filter "name=$(container_name)" --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}'
      exit 0
    fi
    echo "label-studio: not healthy, starting service via docker compose"
    compose up -d
    compose ps
    if ! wait_for_service "${LABEL_STUDIO_CHECK_RETRIES:-20}" "${LABEL_STUDIO_CHECK_INTERVAL_SEC:-3}"; then
      echo "label-studio: startup timeout at $(base_url)" >&2
      exit 1
    fi
    echo "label-studio: healthy at $(base_url)"
    ;;
  stop)
    compose down
    ;;
  logs)
    compose logs -f --tail=100 label-studio
    ;;
  *)
    echo "usage: $0 {ensure|status|check|start|stop|logs}" >&2
    exit 2
    ;;
esac
