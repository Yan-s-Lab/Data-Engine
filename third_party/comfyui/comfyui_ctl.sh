#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.comfyui.yml"
ENV_FILE="${SCRIPT_DIR}/.env"

compose() {
  if [[ -f "${ENV_FILE}" ]]; then
    docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
  else
    docker compose -f "${COMPOSE_FILE}" "$@"
  fi
}

base_url() {
  local host_port="8188"
  if [[ -f "${ENV_FILE}" ]]; then
    host_port="$(grep -E '^COMFYUI_PORT=' "${ENV_FILE}" | tail -n 1 | cut -d'=' -f2- || true)"
    host_port="${host_port:-8188}"
  fi
  printf 'http://127.0.0.1:%s' "${host_port}"
}

container_name() {
  local name="comfyui-service"
  if [[ -f "${ENV_FILE}" ]]; then
    name="$(grep -E '^COMFYUI_CONTAINER_NAME=' "${ENV_FILE}" | tail -n 1 | cut -d'=' -f2- || true)"
    name="${name:-comfyui-service}"
  fi
  printf '%s' "${name}"
}

check_service() {
  local url
  url="$(base_url)"
  curl -fsS "${url}/system_stats" >/dev/null 2>&1
}

cmd="${1:-ensure}"

case "${cmd}" in
  status)
    compose ps
    docker ps --filter "name=$(container_name)" --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}'
    ;;
  check)
    if check_service; then
      echo "comfyui: healthy at $(base_url)"
    else
      echo "comfyui: unavailable at $(base_url)" >&2
      exit 1
    fi
    ;;
  start)
    compose up -d --build
    compose ps
    ;;
  ensure)
    if check_service; then
      echo "comfyui: already healthy at $(base_url)"
      compose ps
      docker ps --filter "name=$(container_name)" --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}'
      exit 0
    fi
    echo "comfyui: not healthy, starting service via docker compose"
    compose up -d --build
    compose ps
    ;;
  stop)
    compose down
    ;;
  logs)
    compose logs -f --tail=100 comfyui
    ;;
  *)
    echo "usage: $0 {ensure|status|check|start|stop|logs}" >&2
    exit 2
    ;;
esac
