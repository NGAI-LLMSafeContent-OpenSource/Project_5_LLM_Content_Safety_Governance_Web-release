#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
AUTODL_DIR="${SCRIPT_DIR}"

log() {
  printf '[llmsafe-autodl] %s\n' "$*"
}

warn() {
  printf '[llmsafe-autodl][warn] %s\n' "$*" >&2
}

die() {
  printf '[llmsafe-autodl][error] %s\n' "$*" >&2
  exit 1
}

load_config() {
  local config_path="${1:-${AUTODL_DIR}/deploy.env}"
  if [[ -f "${config_path}" ]]; then
    # shellcheck source=/dev/null
    source "${config_path}"
  elif [[ -f "${AUTODL_DIR}/deploy.env.example" ]]; then
    # shellcheck source=/dev/null
    source "${AUTODL_DIR}/deploy.env.example"
    warn "using deploy.env.example; copy it to scripts/autodl/deploy.env for AutoDL-specific values"
  else
    die "missing AutoDL deploy config: ${config_path}"
  fi

  DEPLOY_ROOT="${DEPLOY_ROOT:-/root/autodl-tmp/llmsafe}"
  REPOS_DIR="${REPOS_DIR:-${DEPLOY_ROOT}/repos}"
  WWW_DIR="${WWW_DIR:-${DEPLOY_ROOT}/www}"
  LOG_DIR="${LOG_DIR:-${DEPLOY_ROOT}/logs}"
  RUN_DIR="${RUN_DIR:-${DEPLOY_ROOT}/run}"
  DATA_DIR="${DATA_DIR:-${DEPLOY_ROOT}/data}"
  HF_HOME="${HF_HOME:-${DEPLOY_ROOT}/cache/huggingface}"
  MODEL_ROOT="${MODEL_ROOT:-${DEPLOY_ROOT}/models}"

  AUTODL_GATEWAY_HOST="${AUTODL_GATEWAY_HOST:-0.0.0.0}"
  AUTODL_GATEWAY_PORT="${AUTODL_GATEWAY_PORT:-6006}"
  PROJECT5_FRONTEND_ROOT="${PROJECT5_FRONTEND_ROOT:-${WWW_DIR}/project5}"

  PROJECT5_REPO_NAME="${PROJECT5_REPO_NAME:-Project_5_LLM_Content_Safety_Governance_Web}"
  TOPIC1_REPO_NAME="${TOPIC1_REPO_NAME:-Project_1_Construction_of_Evaluation_System}"
  TOPIC1_VALUE_QA_REPO_NAME="${TOPIC1_VALUE_QA_REPO_NAME:-Project_1_Sample_evaluation_Generation}"
  TOPIC1_VALUE_QA_REPO_URL="${TOPIC1_VALUE_QA_REPO_URL:-git@github.com:NGAI-LLMSafeContent/Project_1_Sample_evaluation_Generation.git}"
  TOPIC2_FLYWHEEL_REPO_NAME="${TOPIC2_FLYWHEEL_REPO_NAME:-Project_2_Flywheel_on_Anomaly_Detection_Tracking_Correction}"
  TOPIC2_FILTERGUARD_REPO_NAME="${TOPIC2_FILTERGUARD_REPO_NAME:-Project_2_Anomaly_Data_Identification}"
  TOPIC3_BENCHMARK_REPO_NAME="${TOPIC3_BENCHMARK_REPO_NAME:-Project_3_Risk_Hierarchical_Classification_Benchmark}"
  TOPIC3_CULTURAL_GEN_REPO_NAME="${TOPIC3_CULTURAL_GEN_REPO_NAME:-Project_3_Cultural_Generation_Tool}"
  TOPIC3_DIFFICULTY_REPO_NAME="${TOPIC3_DIFFICULTY_REPO_NAME:-Project_3_Dynamic_Difficulty_Question_Generation_Tool}"

  PROJECT5_DIR="${REPOS_DIR}/${PROJECT5_REPO_NAME}"
  TOPIC1_DIR="${REPOS_DIR}/${TOPIC1_REPO_NAME}"
  TOPIC1_VALUE_QA_DIR="${REPOS_DIR}/${TOPIC1_VALUE_QA_REPO_NAME}"
  TOPIC2_FLYWHEEL_DIR="${REPOS_DIR}/${TOPIC2_FLYWHEEL_REPO_NAME}"
  TOPIC2_FILTERGUARD_DIR="${REPOS_DIR}/${TOPIC2_FILTERGUARD_REPO_NAME}"
  TOPIC3_BENCHMARK_DIR="${REPOS_DIR}/${TOPIC3_BENCHMARK_REPO_NAME}"
  TOPIC3_CULTURAL_GEN_DIR="${REPOS_DIR}/${TOPIC3_CULTURAL_GEN_REPO_NAME}"
  TOPIC3_DIFFICULTY_DIR="${REPOS_DIR}/${TOPIC3_DIFFICULTY_REPO_NAME}"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

resolve_conda() {
  if [[ -n "${CONDA_BIN:-}" ]]; then
    [[ -x "${CONDA_BIN}" ]] || die "CONDA_BIN is not executable: ${CONDA_BIN}"
    printf '%s\n' "${CONDA_BIN}"
    return
  fi
  command -v conda || die "conda not found; set CONDA_BIN in scripts/autodl/deploy.env"
}

ensure_base_dirs() {
  mkdir -p \
    "${DEPLOY_ROOT}" \
    "${REPOS_DIR}" \
    "${WWW_DIR}" \
    "${LOG_DIR}" \
    "${RUN_DIR}" \
    "${DATA_DIR}" \
    "${HF_HOME}" \
    "${MODEL_ROOT}" \
    "${PROJECT5_FRONTEND_ROOT}"
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

start_background() {
  local role="$1"
  shift
  local pid
  ensure_base_dirs
  if is_role_running "${role}"; then
    pid="$(read_pid "${role}")"
    log "${role} already running pid=${pid}"
    return
  fi
  log "starting ${role}; log=$(log_file "${role}")"
  nohup "$@" >"$(log_file "${role}")" 2>&1 &
  pid="$!"
  printf '%s\n' "${pid}" >"$(pid_file "${role}")"
  log "${role} pid=${pid}"
}

stop_role() {
  local role="$1"
  local pid
  pid="$(read_pid "${role}")"
  if ! is_pid_running "${pid}"; then
    log "${role} not running"
    rm -f "$(pid_file "${role}")"
    return
  fi
  log "stopping ${role} pid=${pid}"
  kill "${pid}" >/dev/null 2>&1 || true
  for _ in $(seq 1 20); do
    if ! is_pid_running "${pid}"; then
      rm -f "$(pid_file "${role}")"
      log "${role} stopped"
      return
    fi
    sleep 1
  done
  warn "${role} still running; sending SIGKILL"
  kill -9 "${pid}" >/dev/null 2>&1 || true
  rm -f "$(pid_file "${role}")"
}

service_status_line() {
  local role="$1"
  local pid
  pid="$(read_pid "${role}")"
  if is_pid_running "${pid}"; then
    printf 'running %-24s pid=%-8s log=%s\n' "${role}" "${pid}" "$(log_file "${role}")"
  else
    printf 'down    %-24s log=%s\n' "${role}" "$(log_file "${role}")"
    return 1
  fi
}

http_check() {
  local name="$1"
  local url="$2"
  if curl -fsS --max-time 5 "${url}" >/dev/null; then
    printf 'ok     %-28s %s\n' "${name}" "${url}"
  else
    printf 'failed %-28s %s\n' "${name}" "${url}"
    return 1
  fi
}

run_in_conda() {
  local conda_bin
  conda_bin="$(resolve_conda)"
  "${conda_bin}" run --no-capture-output -n "${CONDA_ENV}" "$@"
}

ensure_conda_env() {
  local env_name="$1"
  local python_version="$2"
  local conda_bin
  conda_bin="$(resolve_conda)"
  if "${conda_bin}" env list | awk '{print $1}' | grep -qx "${env_name}"; then
    log "conda env exists: ${env_name}"
  else
    log "creating conda env: ${env_name}"
    "${conda_bin}" create -y -n "${env_name}" python="${python_version}"
  fi
}

repo_update() {
  local name="$1"
  local url="$2"
  local dir="$3"
  mkdir -p "${REPOS_DIR}"
  require_cmd git
  if [[ -d "${dir}/.git" ]]; then
    log "updating ${name}"
    git -C "${dir}" pull --ff-only
  elif [[ -d "${dir}" ]]; then
    die "${dir} exists but is not a git repository; move it aside or set ${name}_DIR explicitly"
  else
    log "cloning ${name}"
    git clone "${url}" "${dir}"
  fi
}

print_config_summary() {
  cat <<CONFIG
DEPLOY_ROOT=${DEPLOY_ROOT}
REPOS_DIR=${REPOS_DIR}
WWW_DIR=${WWW_DIR}
LOG_DIR=${LOG_DIR}
RUN_DIR=${RUN_DIR}
DATA_DIR=${DATA_DIR}
HF_HOME=${HF_HOME}
MODEL_ROOT=${MODEL_ROOT}
AUTODL_GATEWAY=${AUTODL_GATEWAY_HOST}:${AUTODL_GATEWAY_PORT}
PROJECT5_DIR=${PROJECT5_DIR}
TOPIC1_DIR=${TOPIC1_DIR}
TOPIC1_VALUE_QA_DIR=${TOPIC1_VALUE_QA_DIR}
TOPIC2_FLYWHEEL_DIR=${TOPIC2_FLYWHEEL_DIR}
TOPIC2_FILTERGUARD_DIR=${TOPIC2_FILTERGUARD_DIR}
TOPIC3_BENCHMARK_DIR=${TOPIC3_BENCHMARK_DIR}
TOPIC3_CULTURAL_GEN_DIR=${TOPIC3_CULTURAL_GEN_DIR}
TOPIC3_DIFFICULTY_DIR=${TOPIC3_DIFFICULTY_DIR}
CONFIG
}
