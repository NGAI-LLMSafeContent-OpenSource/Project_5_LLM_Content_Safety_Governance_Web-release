#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT5_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

log() {
  printf '[llmsafe-qwen35] %s\n' "$*"
}

warn() {
  printf '[llmsafe-qwen35][warn] %s\n' "$*" >&2
}

die() {
  printf '[llmsafe-qwen35][error] %s\n' "$*" >&2
  exit 1
}

REMOTE_ROOT="${TOPIC3_QWEN35_REMOTE_ROOT:-/mnt/data1/zx}"
REPOS_DIR="${TOPIC3_QWEN35_REPOS_DIR:-/home/zx/repos}"
TOPIC3_REPO_NAME="${TOPIC3_QWEN35_TOPIC3_REPO_NAME:-Project_3_Dynamic_Difficulty_Question_Generation_Tool}"
TOPIC3_DIR="${TOPIC3_QWEN35_TOPIC3_DIR:-${REPOS_DIR}/${TOPIC3_REPO_NAME}}"
CONDA_ENV="${TOPIC3_QWEN35_CONDA_ENV:-llmsafe-topic3-qwen35-vllm-py310}"
PYTHON_VERSION="${TOPIC3_QWEN35_PYTHON:-3.10}"
VLLM_SPEC="${TOPIC3_QWEN35_VLLM_SPEC:-vllm==0.25.1}"
INSTALL_ROUTER_EDITABLE="${TOPIC3_QWEN35_INSTALL_ROUTER_EDITABLE:-0}"
HF_HOME="${TOPIC3_QWEN35_HF_HOME:-${REMOTE_ROOT}/cache/huggingface}"
MODEL_ROOT="${TOPIC3_QWEN35_MODEL_ROOT:-${REMOTE_ROOT}/models}"
GENERATION_MODEL_DIR="${TOPIC3_QWEN35_GENERATION_MODEL_DIR:-${MODEL_ROOT}/Qwen3.5-9B}"
GUARD_MODEL_DIR="${TOPIC3_QWEN35_GUARD_MODEL_DIR:-${MODEL_ROOT}/Qwen3Guard-Gen-4B}"
RUN_DIR="${TOPIC3_QWEN35_RUN_DIR:-${PROJECT5_DIR}/.codex_tmp/topic3-qwen35-runtime}"
LOG_DIR="${TOPIC3_QWEN35_LOG_DIR:-${RUN_DIR}/logs}"

ROUTER_PORT="${TOPIC3_QWEN35_ROUTER_PORT:-6332}"
GENERATION_PORT="${TOPIC3_QWEN35_GENERATION_PORT:-6333}"
GUARD_PORT="${TOPIC3_QWEN35_GUARD_PORT:-6334}"
GENERATION_GPU="${TOPIC3_QWEN35_GENERATION_GPU:-0}"
GUARD_GPU="${TOPIC3_QWEN35_GUARD_GPU:-1}"
GENERATION_MODEL_NAME="${TOPIC3_QWEN35_GENERATION_MODEL_NAME:-Qwen3.5-9B}"
GUARD_MODEL_NAME="${TOPIC3_QWEN35_GUARD_MODEL_NAME:-Qwen3Guard-Gen-4B}"
GENERATION_GPU_MEMORY_UTILIZATION="${TOPIC3_QWEN35_GENERATION_GPU_MEMORY_UTILIZATION:-0.80}"
GUARD_GPU_MEMORY_UTILIZATION="${TOPIC3_QWEN35_GUARD_GPU_MEMORY_UTILIZATION:-0.65}"
MAX_MODEL_LEN="${TOPIC3_QWEN35_MAX_MODEL_LEN:-8192}"
MODEL_MAP="${TOPIC3_QWEN35_MODEL_MAP:-{\"${GENERATION_MODEL_NAME}\":\"http://127.0.0.1:${GENERATION_PORT}/v1\",\"${GUARD_MODEL_NAME}\":\"http://127.0.0.1:${GUARD_PORT}/v1\"}}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

resolve_conda() {
  if [[ -n "${CONDA_BIN:-}" ]]; then
    [[ -x "${CONDA_BIN}" ]] || die "CONDA_BIN is not executable: ${CONDA_BIN}"
    printf '%s\n' "${CONDA_BIN}"
    return
  fi
  command -v conda || die "conda not found; set CONDA_BIN"
}

run_in_env() {
  local conda_bin
  conda_bin="$(resolve_conda)"
  "${conda_bin}" run --no-capture-output -n "${CONDA_ENV}" "$@"
}

ensure_conda_env() {
  local conda_bin
  conda_bin="$(resolve_conda)"
  if "${conda_bin}" env list | awk '{print $1}' | grep -qx "${CONDA_ENV}"; then
    log "conda env exists: ${CONDA_ENV}"
  else
    log "creating conda env: ${CONDA_ENV}"
    "${conda_bin}" create -y -n "${CONDA_ENV}" python="${PYTHON_VERSION}"
  fi
}

ensure_dirs() {
  mkdir -p "${HF_HOME}" "${RUN_DIR}" "${LOG_DIR}"
}

pid_file() {
  printf '%s/%s.pid\n' "${RUN_DIR}" "$1"
}

log_file() {
  printf '%s/%s.log\n' "${LOG_DIR}" "$1"
}

is_pid_running() {
  local pid="$1"
  [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1
}

pid_pgid() {
  local pid="$1"
  ps -o pgid= -p "${pid}" 2>/dev/null | tr -d '[:space:]' || true
}

read_pid() {
  local role="$1"
  local file
  file="$(pid_file "${role}")"
  [[ -f "${file}" ]] && tr -d '[:space:]' <"${file}" || true
}

is_role_running() {
  local role="$1"
  local pid
  pid="$(read_pid "${role}")"
  is_pid_running "${pid}"
}

check_port_free_for_role() {
  local role="$1"
  local port="$2"
  if is_role_running "${role}"; then
    return
  fi
  if command -v ss >/dev/null 2>&1 && ss -ltn "( sport = :${port} )" | grep -q ":${port}"; then
    die "port ${port} is already listening; stop the existing service or override the port"
  fi
}

port_listener() {
  local port="$1"
  command -v ss >/dev/null 2>&1 || return 1
  ss -ltnp 2>/dev/null | awk -v port=":${port}" '$4 ~ port "$" {print; found=1} END {exit found ? 0 : 1}'
}

pids_for_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
  elif command -v fuser >/dev/null 2>&1; then
    fuser "${port}/tcp" 2>/dev/null | tr ' ' '\n' | sed '/^$/d' || true
  fi
}

wait_http() {
  local label="$1"
  local url="$2"
  local attempts="${3:-120}"
  local interval="${4:-2}"
  for _ in $(seq 1 "${attempts}"); do
    if curl -fsS --max-time 5 "${url}" >/dev/null 2>&1; then
      log "${label} ready: ${url}"
      return 0
    fi
    sleep "${interval}"
  done
  warn "${label} did not become ready: ${url}"
  return 1
}

install_runtime() {
  require_cmd curl
  ensure_dirs
  ensure_conda_env
  [[ -d "${TOPIC3_DIR}/vllm_router" ]] || die "missing Topic 3 router dir: ${TOPIC3_DIR}/vllm_router"

  log "installing Python tooling and vLLM into ${CONDA_ENV}"
  run_in_env python -m pip install --upgrade pip wheel "setuptools<82"
  run_in_env python -m pip install "${VLLM_SPEC}" fastapi uvicorn httpx
  if [[ "${INSTALL_ROUTER_EDITABLE}" == "1" ]]; then
    log "installing Topic 3 vLLM router as editable package"
    run_in_env python -m pip install -e "${TOPIC3_DIR}/vllm_router"
  else
    log "skipping editable router install; router starts with uvicorn --app-dir"
  fi

  log "runtime install complete"
}

assert_model_dirs() {
  [[ -f "${GENERATION_MODEL_DIR}/config.json" ]] || die "missing generation model config: ${GENERATION_MODEL_DIR}/config.json"
  [[ -f "${GUARD_MODEL_DIR}/config.json" ]] || die "missing guard model config: ${GUARD_MODEL_DIR}/config.json"
}

start_background() {
  local role="$1"
  shift
  local pid
  if is_role_running "${role}"; then
    pid="$(read_pid "${role}")"
    log "${role} already running pid=${pid}"
    return
  fi

  local output
  output="$(log_file "${role}")"
  log "starting ${role}; log=${output}"
  require_cmd setsid
  nohup setsid "$@" >"${output}" 2>&1 &
  pid="$!"
  printf '%s\n' "${pid}" >"$(pid_file "${role}")"
  log "${role} pid=${pid}"
}

start_generation() {
  ensure_dirs
  assert_model_dirs
  check_port_free_for_role generation "${GENERATION_PORT}"
  start_background generation env \
    CUDA_VISIBLE_DEVICES="${GENERATION_GPU}" \
    HF_HOME="${HF_HOME}" \
    VLLM_ATTENTION_BACKEND="${VLLM_ATTENTION_BACKEND:-XFORMERS}" \
    VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}" \
    VLLM_USE_FLASHINFER="${VLLM_USE_FLASHINFER:-0}" \
    "$(resolve_conda)" run --no-capture-output -n "${CONDA_ENV}" \
    vllm serve "${GENERATION_MODEL_DIR}" \
      --host 127.0.0.1 \
      --port "${GENERATION_PORT}" \
      --served-model-name "${GENERATION_MODEL_NAME}" \
      --trust-remote-code \
      --gpu-memory-utilization "${GENERATION_GPU_MEMORY_UTILIZATION}" \
      --max-model-len "${MAX_MODEL_LEN}"
  wait_http generation "http://127.0.0.1:${GENERATION_PORT}/v1/models" || true
}

start_guard() {
  ensure_dirs
  assert_model_dirs
  check_port_free_for_role guard "${GUARD_PORT}"
  start_background guard env \
    CUDA_VISIBLE_DEVICES="${GUARD_GPU}" \
    HF_HOME="${HF_HOME}" \
    VLLM_ATTENTION_BACKEND="${VLLM_ATTENTION_BACKEND:-XFORMERS}" \
    VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}" \
    VLLM_USE_FLASHINFER="${VLLM_USE_FLASHINFER:-0}" \
    "$(resolve_conda)" run --no-capture-output -n "${CONDA_ENV}" \
    vllm serve "${GUARD_MODEL_DIR}" \
      --host 127.0.0.1 \
      --port "${GUARD_PORT}" \
      --served-model-name "${GUARD_MODEL_NAME}" \
      --trust-remote-code \
      --gpu-memory-utilization "${GUARD_GPU_MEMORY_UTILIZATION}" \
      --max-model-len "${MAX_MODEL_LEN}"
  wait_http guard "http://127.0.0.1:${GUARD_PORT}/v1/models" || true
}

start_router() {
  ensure_dirs
  [[ -d "${TOPIC3_DIR}/vllm_router" ]] || die "missing Topic 3 router dir: ${TOPIC3_DIR}/vllm_router"
  check_port_free_for_role router "${ROUTER_PORT}"
  start_background router env \
    VLLM_ROUTER_MODEL_MAP="${MODEL_MAP}" \
    "$(resolve_conda)" run --no-capture-output -n "${CONDA_ENV}" \
    python -m uvicorn main:app \
      --app-dir "${TOPIC3_DIR}/vllm_router" \
      --host 127.0.0.1 \
      --port "${ROUTER_PORT}"
  wait_http router "http://127.0.0.1:${ROUTER_PORT}/healthz" || true
}

start_all() {
  start_generation
  start_guard
  start_router
}

stop_role() {
  local role="$1"
  local port="$2"
  local pid
  pid="$(read_pid "${role}")"
  if ! is_pid_running "${pid}"; then
    log "${role} not running"
    stop_port_listeners "${role}" "${port}" TERM
    sleep 1
    stop_port_listeners "${role}" "${port}" KILL
    rm -f "$(pid_file "${role}")"
    return
  fi
  log "stopping ${role} pid=${pid}"
  stop_pid_tree "${pid}" TERM
  for _ in $(seq 1 30); do
    if ! is_pid_running "${pid}" && [[ -z "$(pids_for_port "${port}")" ]]; then
      rm -f "$(pid_file "${role}")"
      log "${role} stopped"
      return
    fi
    sleep 1
  done
  warn "${role} still running; sending SIGKILL"
  stop_pid_tree "${pid}" KILL
  stop_port_listeners "${role}" "${port}" KILL
  rm -f "$(pid_file "${role}")"
}

stop_pid_tree() {
  local pid="$1"
  local signal="$2"
  local pgid
  pgid="$(pid_pgid "${pid}")"
  if [[ "${pgid}" == "${pid}" ]]; then
    kill "-${signal}" "-${pid}" >/dev/null 2>&1 || true
  else
    kill "-${signal}" "${pid}" >/dev/null 2>&1 || true
  fi
}

stop_port_listeners() {
  local role="$1"
  local port="$2"
  local signal="$3"
  local pids
  pids="$(pids_for_port "${port}")"
  [[ -z "${pids}" ]] && return
  warn "${role} has listener(s) on port ${port}; sending SIG${signal}: ${pids//$'\n'/ }"
  while IFS= read -r listener_pid; do
    [[ -n "${listener_pid}" ]] && stop_pid_tree "${listener_pid}" "${signal}"
  done <<<"${pids}"
}

stop_all() {
  stop_role router "${ROUTER_PORT}"
  stop_role guard "${GUARD_PORT}"
  stop_role generation "${GENERATION_PORT}"
}

status_role() {
  local role="$1"
  local url="$2"
  local port="$3"
  local pid
  pid="$(read_pid "${role}")"
  if is_pid_running "${pid}"; then
    printf 'running %-12s pid=%-8s log=%s\n' "${role}" "${pid}" "$(log_file "${role}")"
  else
    local listener
    listener="$(port_listener "${port}" || true)"
    if [[ -n "${listener}" ]]; then
      printf 'external %-12s port=%-6s log=%s\n' "${role}" "${port}" "$(log_file "${role}")"
      printf 'listen  %-12s %s\n' "${role}" "${listener}"
    else
      printf 'down    %-12s log=%s\n' "${role}" "$(log_file "${role}")"
    fi
  fi
  if curl -fsS --max-time 5 "${url}" >/dev/null 2>&1; then
    printf 'ok      %-12s %s\n' "${role}" "${url}"
  else
    printf 'failed  %-12s %s\n' "${role}" "${url}"
  fi
}

status_all() {
  status_role generation "http://127.0.0.1:${GENERATION_PORT}/v1/models" "${GENERATION_PORT}"
  status_role guard "http://127.0.0.1:${GUARD_PORT}/v1/models" "${GUARD_PORT}"
  status_role router "http://127.0.0.1:${ROUTER_PORT}/healthz" "${ROUTER_PORT}"
  curl -fsS --max-time 5 "http://127.0.0.1:${ROUTER_PORT}/v1/models" || true
  printf '\n'
}

smoke() {
  log "checking workers and router"
  curl -fsS "http://127.0.0.1:${GENERATION_PORT}/v1/models"
  printf '\n'
  curl -fsS "http://127.0.0.1:${GUARD_PORT}/v1/models"
  printf '\n'
  curl -fsS "http://127.0.0.1:${ROUTER_PORT}/healthz"
  printf '\n'
  curl -fsS "http://127.0.0.1:${ROUTER_PORT}/v1/models"
  printf '\n'
}

tail_logs() {
  local role="${1:-router}"
  tail -n 120 -f "$(log_file "${role}")"
}

print_config() {
  cat <<CONFIG
PROJECT5_DIR=${PROJECT5_DIR}
TOPIC3_DIR=${TOPIC3_DIR}
CONDA_ENV=${CONDA_ENV}
VLLM_SPEC=${VLLM_SPEC}
INSTALL_ROUTER_EDITABLE=${INSTALL_ROUTER_EDITABLE}
HF_HOME=${HF_HOME}
GENERATION_MODEL_DIR=${GENERATION_MODEL_DIR}
GUARD_MODEL_DIR=${GUARD_MODEL_DIR}
ROUTER_PORT=${ROUTER_PORT}
GENERATION_PORT=${GENERATION_PORT}
GUARD_PORT=${GUARD_PORT}
GENERATION_GPU=${GENERATION_GPU}
GUARD_GPU=${GUARD_GPU}
GENERATION_GPU_MEMORY_UTILIZATION=${GENERATION_GPU_MEMORY_UTILIZATION}
GUARD_GPU_MEMORY_UTILIZATION=${GUARD_GPU_MEMORY_UTILIZATION}
MAX_MODEL_LEN=${MAX_MODEL_LEN}
MODEL_MAP=${MODEL_MAP}
RUN_DIR=${RUN_DIR}
LOG_DIR=${LOG_DIR}
CONFIG
}

usage() {
  cat <<USAGE
Usage: $0 <command>

Commands:
  config             Print resolved configuration.
  install            Create/update env and install vLLM + router dependencies.
  start              Start generation, guard, then router in the background.
  start-generation   Start only Qwen3.5 generation worker.
  start-guard        Start only Qwen3Guard worker.
  start-router       Start only router.
  stop               Stop router, guard, then generation.
  restart            Stop then start all.
  status             Show pid and HTTP readiness.
  smoke              Curl worker/router readiness endpoints.
  logs [role]        Tail logs for role: generation, guard, router.

Default 182 layout:
  Project 5 repo: ${PROJECT5_DIR}
  Topic 3 repo:  ${TOPIC3_DIR}
  Model root:    ${MODEL_ROOT}

Override with TOPIC3_QWEN35_* env vars when needed.
USAGE
}

command="${1:-}"
case "${command}" in
  config)
    print_config
    ;;
  install)
    install_runtime
    ;;
  start)
    start_all
    ;;
  start-generation)
    start_generation
    ;;
  start-guard)
    start_guard
    ;;
  start-router)
    start_router
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    start_all
    ;;
  status)
    status_all
    ;;
  smoke)
    smoke
    ;;
  logs)
    tail_logs "${2:-router}"
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    usage >&2
    die "unknown command: ${command}"
    ;;
esac
