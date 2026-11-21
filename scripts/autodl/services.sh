#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

load_config "${SCRIPT_DIR}/deploy.env"

usage() {
  cat <<USAGE
Usage: $0 <command>

Commands:
  plan             Print the Project 5 no-GPU service plan.
  status           Print Project 5 service status.
  start-project5   Start Project 5 backend and gateway.
  stop-project5    Stop Project 5 gateway and backend.
  restart-project5 Restart Project 5 services.
  smoke            Check Project 5 HTTP readiness.
  logs ROLE        Tail logs for a role.

This service path is safe for AutoDL no-GPU mode. Topic 3 vLLM workers remain
manual and are managed by difficulty-runtime.sh.
USAGE
}

print_core_plan() {
  cat <<PLAN
AutoDL Project 5 no-GPU services:
  gateway                         ${AUTODL_GATEWAY_HOST}:${AUTODL_GATEWAY_PORT}
  project5-backend                127.0.0.1:${PROJECT5_BACKEND_PORT:-5800}
  frontend root                   ${PROJECT5_FRONTEND_ROOT}
PLAN
}

print_status_paths() {
  for role in \
    gateway \
    project5-backend
  do
    printf '%-28s pid=%s log=%s\n' "${role}" "$(pid_file "${role}")" "$(log_file "${role}")"
  done
}

start_project5_backend() {
  [[ -d "${PROJECT5_DIR}/web/backend" ]] || die "missing Project 5 backend dir: ${PROJECT5_DIR}/web/backend; run bootstrap.sh install-project5 first"
  start_background project5-backend env \
    PYTHONPATH=. \
    DATABASE_URL="${PROJECT5_DATABASE_URL:-sqlite+aiosqlite:///${DATA_DIR}/content_governance.db}" \
    CORS_ORIGINS="${PROJECT5_CORS_ORIGINS:-[\"http://127.0.0.1:6006\",\"http://localhost:6006\"]}" \
    BENCHMARK_BASE_URL="${BENCHMARK_BASE_URL:-http://127.0.0.1:${TOPIC3_BENCHMARK_PORT:-6106}}" \
    TOPIC1_PROJECT1_BASE_URL="${TOPIC1_PROJECT1_BASE_URL:-http://127.0.0.1:${TOPIC1_BACKEND_PORT:-6102}}" \
    TOPIC4_INPUT_WORKFLOW_BASE_URL="${TOPIC4_INPUT_WORKFLOW_BASE_URL:-http://127.0.0.1:8081}" \
    CULTURAL_GEN_BASE_URL="${CULTURAL_GEN_BASE_URL:-http://127.0.0.1:${TOPIC3_DIVERSITY_API_PORT:-6322}}" \
    CULTURAL_GEN_DATA_BASE_URL="${CULTURAL_GEN_DATA_BASE_URL:-http://127.0.0.1:${TOPIC3_DIVERSITY_DATA_PORT:-6323}}" \
    TOPIC3_DIFFICULTY_BASE_URL="${TOPIC3_DIFFICULTY_BASE_URL:-http://127.0.0.1:${TOPIC3_DIFFICULTY_PORT:-6331}}" \
    TOPIC3_DIFFICULTY_VLLM_API_BASE="${TOPIC3_DIFFICULTY_VLLM_API_BASE:-http://127.0.0.1:${TOPIC3_DIFFICULTY_ROUTER_PORT:-6332}/v1}" \
    "$(resolve_conda)" run --no-capture-output -n "${CONDA_ENV}" \
      python -m uvicorn app.main:app --host 127.0.0.1 --port "${PROJECT5_BACKEND_PORT:-5800}" \
      --app-dir "${PROJECT5_DIR}/web/backend"
}

start_gateway() {
  [[ -d "${PROJECT5_FRONTEND_ROOT}" ]] || die "missing frontend root: ${PROJECT5_FRONTEND_ROOT}; run bootstrap.sh install-project5 first"
  start_background gateway env \
    AUTODL_GATEWAY_HOST="${AUTODL_GATEWAY_HOST}" \
    AUTODL_GATEWAY_PORT="${AUTODL_GATEWAY_PORT}" \
    PROJECT5_FRONTEND_ROOT="${PROJECT5_FRONTEND_ROOT}" \
    PROJECT5_BACKEND_URL="http://127.0.0.1:${PROJECT5_BACKEND_PORT:-5800}" \
    node "${SCRIPT_DIR}/project5-gateway.mjs"
}

start_project5() {
  ensure_base_dirs
  start_project5_backend
  start_gateway
  log "Project 5 started; open http://127.0.0.1:${AUTODL_GATEWAY_PORT}"
}

stop_project5() {
  stop_role gateway
  stop_role project5-backend
}

status_project5() {
  local failed=0
  service_status_line project5-backend || failed=1
  service_status_line gateway || failed=1
  return "${failed}"
}

smoke_project5() {
  local failed=0
  http_check "project5-backend" "http://127.0.0.1:${PROJECT5_BACKEND_PORT:-5800}/health" || failed=1
  http_check "project5-gateway" "http://127.0.0.1:${AUTODL_GATEWAY_PORT}" || failed=1
  http_check "project5-api-same-origin" "http://127.0.0.1:${AUTODL_GATEWAY_PORT}/api/health" || failed=1
  return "${failed}"
}

command="${1:-}"
case "${command}" in
  plan)
    print_core_plan
    ;;
  status)
    status_project5
    ;;
  start-project5|start-core)
    start_project5
    ;;
  stop-project5|stop-core)
    stop_project5
    ;;
  restart-project5)
    stop_project5
    start_project5
    ;;
  smoke)
    smoke_project5
    ;;
  logs)
    role="${2:-gateway}"
    tail -n 120 -f "$(log_file "${role}")"
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    usage >&2
    die "unknown command: ${command}"
    ;;
esac
