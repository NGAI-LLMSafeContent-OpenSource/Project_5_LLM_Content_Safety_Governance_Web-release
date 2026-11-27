#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

lower() {
  printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]'
}

bool_true() {
  case "$(lower "${1:-}")" in
    true|1|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

# Every Topic repo lives under one GitHub org. Defaulting the clone URL from the
# repo name keeps a hand-trimmed deploy.env (only the values that differ from the
# example) valid, instead of aborting later in deploy-all on `set -u`.
default_repo_url() {
  printf 'git@github.com:%s/%s.git' "${GITHUB_ORG:-NGAI-LLMSafeContent}" "$1"
}

log() {
  printf '[llmsafe] %s\n' "$*"
}

warn() {
  printf '[llmsafe][warn] %s\n' "$*" >&2
}

die() {
  printf '[llmsafe][error] %s\n' "$*" >&2
  exit 1
}

load_config() {
  local config_path="${1:-${SERVER_DIR}/deploy.env}"
  if [[ -f "${config_path}" ]]; then
    # shellcheck source=/dev/null
    source "${config_path}"
  elif [[ -f "${SERVER_DIR}/deploy.env.example" ]]; then
    # shellcheck source=/dev/null
    source "${SERVER_DIR}/deploy.env.example"
    warn "using deploy.env.example; copy it to scripts/server/deploy.env for server-specific values"
  else
    die "missing deploy config: ${config_path}"
  fi

  DEPLOY_ROOT="${DEPLOY_ROOT:-/data/zhangxu}"
  REPOS_DIR="${REPOS_DIR:-${DEPLOY_ROOT}/repos}"
  WWW_DIR="${WWW_DIR:-${DEPLOY_ROOT}/www}"
  LOG_DIR="${LOG_DIR:-${DEPLOY_ROOT}/logs}"
  CONDA_ENV="${CONDA_ENV:-llmsafe-py310}"
  PUBLIC_HOST="${PUBLIC_HOST:-platform.example.invalid}"
  PROJECT5_FRONTEND_ROOT="${PROJECT5_FRONTEND_ROOT:-${WWW_DIR}/project5}"
  PROJECT5_NGINX_SITE_NAME="${PROJECT5_NGINX_SITE_NAME:-llmsafe-project5}"
  TOPIC3_COMPLIANCE_PORT="${TOPIC3_COMPLIANCE_PORT:-6311}"
  COMPLIANCE_EDIT_BASE_URL="${COMPLIANCE_EDIT_BASE_URL:-http://127.0.0.1:${TOPIC3_COMPLIANCE_PORT}}"
  COMPLIANCE_EDIT_TIMEOUT_SECONDS="${COMPLIANCE_EDIT_TIMEOUT_SECONDS:-300}"

  # Port map defaults live here (single source of truth) so a hand-trimmed
  # deploy.env still resolves to the same ports every script used to hardcode.
  PROJECT5_FRONTEND_PORT="${PROJECT5_FRONTEND_PORT:-5173}"
  PROJECT5_BACKEND_PORT="${PROJECT5_BACKEND_PORT:-5800}"
  TOPIC3_BENCHMARK_PORT="${TOPIC3_BENCHMARK_PORT:-6006}"
  TOPIC3_DIVERSITY_UI_PORT="${TOPIC3_DIVERSITY_UI_PORT:-6321}"
  TOPIC3_DIVERSITY_API_PORT="${TOPIC3_DIVERSITY_API_PORT:-6322}"
  TOPIC3_DIVERSITY_DATA_PORT="${TOPIC3_DIVERSITY_DATA_PORT:-6323}"
  TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_PORT="${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_PORT:-8877}"
  TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_V2_PORT="${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_V2_PORT:-8878}"
  TOPIC3_DIFFICULTY_PORT="${TOPIC3_DIFFICULTY_PORT:-6331}"
  TOPIC3_DIFFICULTY_ROUTER_PORT="${TOPIC3_DIFFICULTY_ROUTER_PORT:-6332}"
  TOPIC3_DIFFICULTY_GENERATION_WORKER_PORT="${TOPIC3_DIFFICULTY_GENERATION_WORKER_PORT:-6333}"
  TOPIC3_DIFFICULTY_GUARD_WORKER_PORT="${TOPIC3_DIFFICULTY_GUARD_WORKER_PORT:-6334}"
  TOPIC1_FRONTEND_PORT="${TOPIC1_FRONTEND_PORT:-6101}"
  TOPIC1_BACKEND_PORT="${TOPIC1_BACKEND_PORT:-6102}"
  TOPIC2_SHOWCASE_PORT="${TOPIC2_SHOWCASE_PORT:-6201}"
  TOPIC2_FILTERGUARD_PORT="${TOPIC2_FILTERGUARD_PORT:-6211}"
  TOPIC2_DYNBENCH_PORT="${TOPIC2_DYNBENCH_PORT:-8766}"

  PROJECT5_REPO_NAME="${PROJECT5_REPO_NAME:-Project_5_LLM_Content_Safety_Governance_Web}"
  PROJECT5_REPO_URL="${PROJECT5_REPO_URL:-$(default_repo_url "${PROJECT5_REPO_NAME}")}"
  TOPIC1_REPO_NAME="${TOPIC1_REPO_NAME:-Project_1_Construction_of_Evaluation_System}"
  TOPIC1_REPO_URL="${TOPIC1_REPO_URL:-$(default_repo_url "${TOPIC1_REPO_NAME}")}"
  TOPIC1_VALUE_QA_REPO_NAME="${TOPIC1_VALUE_QA_REPO_NAME:-Project_1_Sample_evaluation_Generation}"
  TOPIC1_VALUE_QA_REPO_URL="${TOPIC1_VALUE_QA_REPO_URL:-$(default_repo_url "${TOPIC1_VALUE_QA_REPO_NAME}")}"
  TOPIC2_FLYWHEEL_REPO_NAME="${TOPIC2_FLYWHEEL_REPO_NAME:-Project_2_Flywheel_on_Anomaly_Detection_Tracking_Correction}"
  TOPIC2_FLYWHEEL_REPO_URL="${TOPIC2_FLYWHEEL_REPO_URL:-$(default_repo_url "${TOPIC2_FLYWHEEL_REPO_NAME}")}"
  TOPIC2_FILTERGUARD_REPO_NAME="${TOPIC2_FILTERGUARD_REPO_NAME:-Project_2_Anomaly_Data_Identification}"
  TOPIC2_FILTERGUARD_REPO_URL="${TOPIC2_FILTERGUARD_REPO_URL:-$(default_repo_url "${TOPIC2_FILTERGUARD_REPO_NAME}")}"
  TOPIC3_BENCHMARK_REPO_NAME="${TOPIC3_BENCHMARK_REPO_NAME:-Project_3_Risk_Hierarchical_Classification_Benchmark}"
  TOPIC3_BENCHMARK_REPO_URL="${TOPIC3_BENCHMARK_REPO_URL:-$(default_repo_url "${TOPIC3_BENCHMARK_REPO_NAME}")}"
  TOPIC3_CULTURAL_GEN_REPO_NAME="${TOPIC3_CULTURAL_GEN_REPO_NAME:-Project_3_Cultural_Generation_Tool}"
  TOPIC3_CULTURAL_GEN_REPO_URL="${TOPIC3_CULTURAL_GEN_REPO_URL:-$(default_repo_url "${TOPIC3_CULTURAL_GEN_REPO_NAME}")}"
  TOPIC3_CULTURAL_CORPUS_REPO_NAME="${TOPIC3_CULTURAL_CORPUS_REPO_NAME:-Project_3_Cultural_Diversity_Corpus_Generation_Tool}"
  TOPIC3_CULTURAL_CORPUS_REPO_URL="${TOPIC3_CULTURAL_CORPUS_REPO_URL:-$(default_repo_url "${TOPIC3_CULTURAL_CORPUS_REPO_NAME}")}"
  TOPIC3_CULTURAL_ASSESSMENT_REPO_NAME="${TOPIC3_CULTURAL_ASSESSMENT_REPO_NAME:-Project_3_Cultural_Diversity_Assessment_Tool}"
  TOPIC3_CULTURAL_ASSESSMENT_REPO_URL="${TOPIC3_CULTURAL_ASSESSMENT_REPO_URL:-$(default_repo_url "${TOPIC3_CULTURAL_ASSESSMENT_REPO_NAME}")}"
  TOPIC3_DIFFICULTY_REPO_NAME="${TOPIC3_DIFFICULTY_REPO_NAME:-Project_3_Dynamic_Difficulty_Question_Generation_Tool}"
  TOPIC3_DIFFICULTY_REPO_URL="${TOPIC3_DIFFICULTY_REPO_URL:-$(default_repo_url "${TOPIC3_DIFFICULTY_REPO_NAME}")}"
  TOPIC3_DIFFICULTY_CONDA_ENV="${TOPIC3_DIFFICULTY_CONDA_ENV:-llmsafe-topic3-difficulty-py312}"
  TOPIC3_DIFFICULTY_PYTHON="${TOPIC3_DIFFICULTY_PYTHON:-3.12}"
  TOPIC3_DIFFICULTY_HF_HOME="${TOPIC3_DIFFICULTY_HF_HOME:-${DEPLOY_ROOT}/cache/huggingface}"
  TOPIC3_DIFFICULTY_START_LOCAL_INFERENCE="${TOPIC3_DIFFICULTY_START_LOCAL_INFERENCE:-true}"
  # Governance confirm→detect path; off only stops the worker (API/session still up).
  PROJECT5_GOVERNANCE_WORKER_ENABLED="${PROJECT5_GOVERNANCE_WORKER_ENABLED:-true}"
  TOPIC3_COMPLIANCE_REPO_NAME="${TOPIC3_COMPLIANCE_REPO_NAME:-Project_3_Compliance_Editing_Tool}"
  TOPIC3_COMPLIANCE_REPO_URL="${TOPIC3_COMPLIANCE_REPO_URL:-$(default_repo_url "${TOPIC3_COMPLIANCE_REPO_NAME}")}"
  TOPIC3_RISK_REPO_NAME="${TOPIC3_RISK_REPO_NAME:-Project_3_Dynamic_Risk_Benchmark_Generation}"
  TOPIC3_RISK_REPO_URL="${TOPIC3_RISK_REPO_URL:-$(default_repo_url "${TOPIC3_RISK_REPO_NAME}")}"
  TOPIC3_RISK_AGENT_PORT="${TOPIC3_RISK_AGENT_PORT:-6351}"
  TOPIC3_RISK_QWEN_PORT="${TOPIC3_RISK_QWEN_PORT:-6352}"
  TOPIC3_RISK_AGENT_URL="${TOPIC3_RISK_AGENT_URL:-http://127.0.0.1:${TOPIC3_RISK_AGENT_PORT}/chat}"
  TOPIC3_RISK_QWEN_API_BASE="${TOPIC3_RISK_QWEN_API_BASE:-http://127.0.0.1:${TOPIC3_RISK_QWEN_PORT}/v1}"

  PROJECT5_DIR="${REPOS_DIR}/${PROJECT5_REPO_NAME}"
  TOPIC1_DIR="${REPOS_DIR}/${TOPIC1_REPO_NAME}"
  TOPIC1_VALUE_QA_DIR="${TOPIC1_VALUE_QA_PROJECT_ROOT:-${REPOS_DIR}/${TOPIC1_VALUE_QA_REPO_NAME}}"
  TOPIC1_VALUE_QA_PROJECT_ROOT="${TOPIC1_VALUE_QA_PROJECT_ROOT:-${TOPIC1_VALUE_QA_DIR}}"
  TOPIC1_VALUE_QA_PYTHON="${TOPIC1_VALUE_QA_PYTHON:-${TOPIC1_VALUE_QA_DIR}/.venv/bin/python}"
  TOPIC2_FLYWHEEL_DIR="${REPOS_DIR}/${TOPIC2_FLYWHEEL_REPO_NAME}"
  TOPIC2_FILTERGUARD_DIR="${REPOS_DIR}/${TOPIC2_FILTERGUARD_REPO_NAME}"
  TOPIC3_BENCHMARK_DIR="${REPOS_DIR}/${TOPIC3_BENCHMARK_REPO_NAME}"
  TOPIC3_CULTURAL_GEN_DIR="${REPOS_DIR}/${TOPIC3_CULTURAL_GEN_REPO_NAME}"
  TOPIC3_CULTURAL_CORPUS_DIR="${REPOS_DIR}/${TOPIC3_CULTURAL_CORPUS_REPO_NAME}"
  CULTURAL_CORPUS_GENERATOR_ROOT="${CULTURAL_CORPUS_GENERATOR_ROOT:-${TOPIC3_CULTURAL_CORPUS_DIR}/framework}"
  CULTURAL_CORPUS_RUNS_DIR="${CULTURAL_CORPUS_RUNS_DIR:-${CULTURAL_CORPUS_GENERATOR_ROOT}/runs}"
  TOPIC3_CULTURAL_ASSESSMENT_DIR="${REPOS_DIR}/${TOPIC3_CULTURAL_ASSESSMENT_REPO_NAME}"
  CULTURAL_ASSESSMENT_ROOT="${CULTURAL_ASSESSMENT_ROOT:-${TOPIC3_CULTURAL_ASSESSMENT_DIR}}"
  CULTURAL_ASSESSMENT_CONSOLE_BASE_URL="${CULTURAL_ASSESSMENT_CONSOLE_BASE_URL:-http://127.0.0.1:${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_PORT:-8877}}"
  CULTURAL_ASSESSMENT_CONSOLE_V2_BASE_URL="${CULTURAL_ASSESSMENT_CONSOLE_V2_BASE_URL:-http://127.0.0.1:${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_V2_PORT:-8878}}"
  TOPIC3_DIFFICULTY_DIR="${REPOS_DIR}/${TOPIC3_DIFFICULTY_REPO_NAME}"
  TOPIC3_DIFFICULTY_VLLM_API_BASE="${TOPIC3_DIFFICULTY_VLLM_API_BASE:-http://127.0.0.1:${TOPIC3_DIFFICULTY_ROUTER_PORT:-6332}/v1}"
  TOPIC3_COMPLIANCE_DIR="${REPOS_DIR}/${TOPIC3_COMPLIANCE_REPO_NAME}"
  TOPIC3_RISK_DIR="${REPOS_DIR}/${TOPIC3_RISK_REPO_NAME}"
  TOPIC3_RISK_BENCHMARK_PROJECT_ROOT="${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT:-${TOPIC3_RISK_DIR}}"
  TOPIC3_RISK_BENCHMARK_PYTHON="${TOPIC3_RISK_BENCHMARK_PYTHON:-}"
  TOPIC3_RISK_CONDA_ENV="${TOPIC3_RISK_CONDA_ENV:-llmsafe-topic3-risk-py310}"
  TOPIC3_RISK_QWEN_MODEL="${TOPIC3_RISK_QWEN_MODEL:-${TOPIC3_DIFFICULTY_GENERATION_MODEL_NAME:-Qwen3.5-9B}}"
  TOPIC3_RISK_QWEN_API_KEY="${TOPIC3_RISK_QWEN_API_KEY:-EMPTY}"
  TOPIC3_RISK_REUSE_DIFFICULTY_QWEN="${TOPIC3_RISK_REUSE_DIFFICULTY_QWEN:-true}"
  TOPIC3_RISK_SKILLS_WORKSPACE_ROOT="${TOPIC3_RISK_SKILLS_WORKSPACE_ROOT:-${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}/risk_skills_v3}"
  if topic3_risk_reuses_difficulty_qwen; then
    TOPIC3_RISK_QWEN_API_BASE="${TOPIC3_DIFFICULTY_VLLM_API_BASE}"
  fi

  # Deployment orchestration knobs. Defaults reproduce the historical behaviour:
  # deploy every component, abort on the first failure, execute for real.
  DEPLOY_COMPONENTS="${DEPLOY_COMPONENTS:-all}"
  DEPLOY_STRICT="${DEPLOY_STRICT:-true}"
  DEPLOY_DRY_RUN="${DEPLOY_DRY_RUN:-false}"
}

is_dry_run() {
  bool_true "${DEPLOY_DRY_RUN:-false}"
}

deploy_strict() {
  local value
  value="$(lower "${DEPLOY_STRICT:-true}")"
  case "${value}" in
    true|1|yes|on)
      return 0
      ;;
    false|0|no|off)
      return 1
      ;;
    *)
      die "DEPLOY_STRICT must be true/false, 1/0, yes/no, or on/off"
      ;;
  esac
}

# DEPLOY_COMPONENTS="all" or a comma/space separated list, e.g.
# "project5,topic3-benchmark". Used to skip work and to re-run a single
# component after a tolerated failure.
component_enabled() {
  local name="$1"
  local item
  for item in ${DEPLOY_COMPONENTS//,/ }; do
    case "${item}" in
      all|"${name}") return 0 ;;
    esac
  done
  return 1
}

# Echo a mutating command in dry-run mode, run it otherwise.
run_mutation() {
  if is_dry_run; then
    printf '[dry-run] %s\n' "$*" >&2
    return 0
  fi
  "$@"
}

# Stop a failing step from aborting the whole deploy when DEPLOY_STRICT=false.
# With DEPLOY_STRICT=true (default) the command runs unchanged and keeps the
# historical "abort on first failure" semantics.
protected() {
  local label="$1"
  shift
  if deploy_strict; then
    "$@"
    return
  fi
  if ! "$@"; then
    warn "tolerated failure: ${label}"
  fi
  return 0
}

# Dry-run hook: `sudo` is used directly throughout these scripts, so shadowing
# it (and delegating to `command sudo`) is the only way to make `--dry-run`
# reach every systemd/nginx/rsync call. Outside dry-run this is a pass-through.
sudo() {
  if is_dry_run; then
    printf '[dry-run] sudo %s\n' "$*" >&2
    return 0
  fi
  command sudo "$@"
}

config_key_known() {
  local key="$1"
  grep -rqE "(\\$\\{${key}[^A-Z0-9_]|^[[:space:]]*(export[[:space:]]+)?${key}=)" \
    "${SERVER_DIR}" --include='*.sh' 2>/dev/null ||
    grep -qE "^[[:space:]]*#?[[:space:]]*${key}=" "${SERVER_DIR}/deploy.env.example" 2>/dev/null
}

# Read-only sanity check. Never dies: today a bad deploy.env only surfaces deep
# inside deploy-all (after systemd/nginx were already modified), so surface it
# early as warnings instead of blocking a deploy that used to succeed.
validate_config() {
  local config_path="${1:-${SERVER_DIR}/deploy.env}"
  local problems=0
  local port_var
  local value
  local line
  local key
  local port_vars=(
    PROJECT5_FRONTEND_PORT
    PROJECT5_BACKEND_PORT
    TOPIC3_BENCHMARK_PORT
    TOPIC3_COMPLIANCE_PORT
    TOPIC3_DIVERSITY_UI_PORT
    TOPIC3_DIVERSITY_API_PORT
    TOPIC3_DIVERSITY_DATA_PORT
    TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_PORT
    TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_V2_PORT
    TOPIC3_DIFFICULTY_PORT
    TOPIC3_DIFFICULTY_ROUTER_PORT
    TOPIC3_DIFFICULTY_GENERATION_WORKER_PORT
    TOPIC3_DIFFICULTY_GUARD_WORKER_PORT
    TOPIC3_RISK_AGENT_PORT
    TOPIC3_RISK_QWEN_PORT
    TOPIC1_FRONTEND_PORT
    TOPIC1_BACKEND_PORT
    TOPIC2_SHOWCASE_PORT
    TOPIC2_FILTERGUARD_PORT
    TOPIC2_DYNBENCH_PORT
  )

  for port_var in "${port_vars[@]}"; do
    value="${!port_var:-}"
    if [[ -z "${value}" ]]; then
      warn "config: ${port_var} is empty"
      problems=$((problems + 1))
    elif [[ ! "${value}" =~ ^[0-9]+$ ]]; then
      warn "config: ${port_var}=${value} is not a port number"
      problems=$((problems + 1))
    fi
  done

  if [[ "${PUBLIC_HOST}" == *"://"* || "${PUBLIC_HOST}" == */* || "${PUBLIC_HOST}" == *:* ]]; then
    warn "config: PUBLIC_HOST must be a bare host (no scheme, port or path); got ${PUBLIC_HOST}"
    problems=$((problems + 1))
  fi

  case "$(lower "${DEPLOY_DRY_RUN:-false}")" in
    true|1|yes|on|false|0|no|off) ;;
    *)
      warn "config: DEPLOY_DRY_RUN must be true/false, 1/0, yes/no, or on/off"
      problems=$((problems + 1))
      ;;
  esac
  case "$(lower "${DEPLOY_STRICT:-true}")" in
    true|1|yes|on|false|0|no|off) ;;
    *)
      warn "config: DEPLOY_STRICT must be true/false, 1/0, yes/no, or on/off"
      problems=$((problems + 1))
      ;;
  esac

  if [[ -f "${config_path}" ]]; then
    while IFS= read -r line || [[ -n "${line}" ]]; do
      line="${line#"${line%%[![:space:]]*}"}"
      [[ -z "${line}" || "${line}" == \#* ]] && continue
      line="${line#export }"
      key="${line%%=*}"
      [[ "${key}" == "${line}" ]] && continue
      key="${key%"${key##*[![:space:]]}"}"
      [[ -z "${key}" ]] && continue
      if ! config_key_known "${key}"; then
        warn "config: ${config_path} sets ${key}, but no deploy script reads it (typo?)"
        problems=$((problems + 1))
      fi
    done < "${config_path}"
  fi

  if ((problems > 0)); then
    warn "config: ${problems} problem(s) above; deploy continues (validate is advisory)"
  else
    log "config: no problems detected in ${config_path}"
  fi
  return 0
}

# Stable KEY=value dump used to prove a refactor does not change how a given
# deploy.env resolves (run it on the production host before/after the change).
dump_config() {
  local var
  {
    for var in $(compgen -v); do
      case "${var}" in
        DEPLOY_*|GITHUB_ORG|REPOS_DIR|WWW_DIR|LOG_DIR|PUBLIC_HOST|CONDA_*|\
        PROJECT5_*|PROJECT1_*|PROJECT4_*|TOPIC1_*|TOPIC2_*|TOPIC3_*|TOPIC4_*|\
        CULTURAL_*|COMPLIANCE_*|BENCHMARK_*|OUTPUT_*)
          printf '%s=%s\n' "${var}" "${!var}"
          ;;
      esac
    done
  } | sort
}

topic3_difficulty_starts_local_inference() {
  local value
  value="$(printf '%s' "${TOPIC3_DIFFICULTY_START_LOCAL_INFERENCE:-true}" | tr '[:upper:]' '[:lower:]')"
  case "${value}" in
    true|1|yes|on)
      return 0
      ;;
    false|0|no|off)
      return 1
      ;;
    *)
      die "TOPIC3_DIFFICULTY_START_LOCAL_INFERENCE must be true/false, 1/0, yes/no, or on/off"
      ;;
  esac
}

project5_governance_worker_enabled() {
  local value
  value="$(printf '%s' "${PROJECT5_GOVERNANCE_WORKER_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')"
  case "${value}" in
    true|1|yes|on)
      return 0
      ;;
    false|0|no|off)
      return 1
      ;;
    *)
      die "PROJECT5_GOVERNANCE_WORKER_ENABLED must be true/false, 1/0, yes/no, or on/off"
      ;;
  esac
}

install_project5_governance_worker_unit() {
  local conda_bin
  conda_bin="$(resolve_conda)"
  # Same WorkingDirectory as backend so pydantic Settings picks up web/backend/.env
  # (Activation Probe / FilterGuard / DB). Independent process per ADR 0004.
  install_systemd_unit "llmsafe-project5-governance-worker" "[Unit]
Description=LLMSafe Project 5 governance task worker (confirm → detect)
After=network.target llmsafe-project5-backend.service

[Service]
Type=simple
WorkingDirectory=${PROJECT5_DIR}/web/backend
Environment=PYTHONPATH=.
Environment=PYTHONUNBUFFERED=1
Environment=TOPIC2_FILTERGUARD_BASE_URL=${TOPIC2_FILTERGUARD_BASE_URL:-http://127.0.0.1:${TOPIC2_FILTERGUARD_PORT:-6211}}
Environment=TOPIC2_FILTERGUARD_METHOD=${TOPIC2_FILTERGUARD_METHOD:-keyword}
Environment=TOPIC2_FILTERGUARD_TIMEOUT_SECONDS=${TOPIC2_FILTERGUARD_TIMEOUT_SECONDS:-10}
ExecStart=${conda_bin} run --no-capture-output -n ${CONDA_ENV} python -m app.workers.governance_task_worker
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"
}

enable_project5_governance_worker() {
  if project5_governance_worker_enabled; then
    sudo systemctl enable llmsafe-project5-governance-worker
  else
    sudo systemctl disable --now llmsafe-project5-governance-worker 2>/dev/null || true
    log "Project 5 governance worker disabled via PROJECT5_GOVERNANCE_WORKER_ENABLED"
  fi
}

topic3_risk_reuses_difficulty_qwen() {
  local value
  value="$(printf '%s' "${TOPIC3_RISK_REUSE_DIFFICULTY_QWEN:-true}" | tr '[:upper:]' '[:lower:]')"
  case "${value}" in
    true|1|yes|on)
      return 0
      ;;
    false|0|no|off)
      return 1
      ;;
    *)
      die "TOPIC3_RISK_REUSE_DIFFICULTY_QWEN must be true/false, 1/0, yes/no, or on/off"
      ;;
  esac
}

topic3_risk_snapshot_ready() {
  [[ -f "${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}/qwen_agent_server/agent_server.py" ]] &&
    [[ -f "${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}/qwen_agent_server/live_run_adapter.py" ]]
}

install_topic3_risk_agent_unit() {
  local conda_bin
  conda_bin="$(resolve_conda)"
  install_systemd_unit "llmsafe-topic3-risk-agent" "[Unit]
Description=LLMSafe Topic 3 dynamic risk Agent (no GPU)
After=network.target

[Service]
Type=simple
WorkingDirectory=${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}/qwen_agent_server
Environment=QWEN_BASE_URL=${TOPIC3_RISK_QWEN_API_BASE}
Environment=QWEN_MODEL=${TOPIC3_RISK_QWEN_MODEL}
Environment=QWEN_API_KEY=${TOPIC3_RISK_QWEN_API_KEY}
Environment=SKILLS_WORKSPACE_ROOT=${TOPIC3_RISK_SKILLS_WORKSPACE_ROOT}
Environment=PYTHONUNBUFFERED=1
ExecStart=${conda_bin} run --no-capture-output -n ${TOPIC3_RISK_CONDA_ENV} python -m uvicorn agent_server:app --host 127.0.0.1 --port ${TOPIC3_RISK_AGENT_PORT:-6351}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"
}

enable_topic3_risk_agent() {
  if topic3_risk_snapshot_ready; then
    sudo systemctl enable llmsafe-topic3-risk-agent
  else
    sudo systemctl disable --now llmsafe-topic3-risk-agent 2>/dev/null || true
    warn "topic3-risk snapshot missing; llmsafe-topic3-risk-agent not enabled"
  fi
}

resolve_uv() {
  if command -v uv >/dev/null 2>&1; then
    command -v uv
    return
  fi
  local user_uv="${HOME}/.local/bin/uv"
  if [[ -x "${user_uv}" ]]; then
    printf '%s\n' "${user_uv}"
    return
  fi
  die "uv not found; install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
}

topic3_compliance_ready() {
  [[ -f "${TOPIC3_COMPLIANCE_DIR}/editing_api/pyproject.toml" ]]
}

install_topic3_compliance_unit() {
  local uv_bin
  uv_bin="$(resolve_uv)"
  local router_api_base="http://127.0.0.1:${TOPIC3_DIFFICULTY_ROUTER_PORT:-6332}/v1"
  install_systemd_unit "llmsafe-topic3-compliance" "[Unit]
Description=LLMSafe Topic 3 compliance editing API
After=network.target

[Service]
Type=simple
WorkingDirectory=${TOPIC3_COMPLIANCE_DIR}
Environment=COMPLIANCE_EDITOR_API_BASE=${router_api_base}
Environment=COMPLIANCE_EDITOR_MODEL=Qwen3.5-9B
Environment=COMPLIANCE_GUARD_API_BASE=${router_api_base}
Environment=COMPLIANCE_GUARD_MODEL=Qwen3Guard-Gen-4B
Environment=COMPLIANCE_TRANSLATOR_API_BASE=${router_api_base}
Environment=COMPLIANCE_TRANSLATOR_MODEL=Hy-MT2-7B
Environment=COMPLIANCE_EDITOR_TIMEOUT=90
Environment=COMPLIANCE_GUARD_TIMEOUT=60
Environment=COMPLIANCE_TRANSLATOR_TIMEOUT=120
ExecStart=${uv_bin} run --project editing_api uvicorn main:app --app-dir editing_api --host 127.0.0.1 --port ${TOPIC3_COMPLIANCE_PORT:-6311}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"
}

enable_topic3_compliance() {
  if topic3_compliance_ready; then
    sudo systemctl enable llmsafe-topic3-compliance
  else
    sudo systemctl disable --now llmsafe-topic3-compliance 2>/dev/null || true
    warn "topic3-compliance repo missing at ${TOPIC3_COMPLIANCE_DIR}; llmsafe-topic3-compliance not enabled until repo is cloned"
  fi
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
  command -v conda || die "conda not found; set CONDA_BIN in scripts/server/deploy.env"
}

run_in_conda() {
  local conda_bin
  conda_bin="$(resolve_conda)"
  run_mutation "${conda_bin}" run -n "${CONDA_ENV}" "$@"
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
    run_mutation "${conda_bin}" create -y -n "${env_name}" python="${python_version}"
  fi
}

repo_update() {
  local name="$1"
  local url="$2"
  local dir="$3"
  run_mutation mkdir -p "${REPOS_DIR}"
  require_cmd git
  if [[ -d "${dir}/.git" ]]; then
    log "updating ${name}"
    run_mutation git -C "${dir}" pull --ff-only
  elif [[ -d "${dir}" ]]; then
    die "${dir} exists but is not a git repository; move it aside or clone ${url}"
  else
    log "cloning ${name}"
    run_mutation git clone "${url}" "${dir}"
  fi
}

# Local snapshot only: never git clone / pull. Deploy continues if the tree is
# already present; missing tree only warns (optional live_run CLI).
ensure_local_snapshot_repo() {
  local name="$1"
  local dir="$2"
  run_mutation mkdir -p "${REPOS_DIR}"
  if [[ -d "${dir}" ]]; then
    log "skip git update for ${name} (local snapshot at ${dir})"
  else
    warn "${name} local snapshot missing at ${dir}; risk live_run CLI will be unavailable until the tree is synced manually"
  fi
}

install_systemd_unit() {
  local service_name="$1"
  local unit_body="$2"
  local target="/etc/systemd/system/${service_name}.service"
  log "installing ${target}"
  printf '%s\n' "${unit_body}" | sudo tee "${target}" >/dev/null
}

install_project5_nginx_site() {
  log "installing Project 5 nginx site"
  sudo tee "/etc/nginx/sites-available/${PROJECT5_NGINX_SITE_NAME}" >/dev/null <<NGINX
server {
    listen ${PROJECT5_FRONTEND_PORT:-5173};
    server_name ${PUBLIC_HOST};

    root ${PROJECT5_FRONTEND_ROOT};
    index index.html;

    location = /api/health {
        proxy_pass http://127.0.0.1:${PROJECT5_BACKEND_PORT:-5800}/health;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 900s;
        proxy_read_timeout 900s;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:${PROJECT5_BACKEND_PORT:-5800}/api/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        # culture-batch / live-batch etc. are sync long requests; default 60s causes 504
        proxy_connect_timeout 60s;
        proxy_send_timeout 900s;
        proxy_read_timeout 900s;
    }

    location /compliance/ {
        proxy_pass http://127.0.0.1:${TOPIC3_COMPLIANCE_PORT:-6311}/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 900s;
        proxy_read_timeout 900s;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
NGINX
  sudo mkdir -p /etc/nginx/sites-enabled
  sudo ln -sf "/etc/nginx/sites-available/${PROJECT5_NGINX_SITE_NAME}" \
    "/etc/nginx/sites-enabled/${PROJECT5_NGINX_SITE_NAME}"
  sudo nginx -t
}

# nginx runs as www-data. A deploy root created with a 027 umask (e.g. 750) makes
# every static request fail with 403/500 even though the build and rsync both
# succeeded. Probe first so an already-working host is left untouched.
ensure_nginx_can_read() {
  local root="$1"
  if is_dry_run; then
    printf '[dry-run] sudo -u www-data test -r %s || grant www-data read access\n' "${root}" >&2
    return 0
  fi
  if [[ ! -d "${root}" ]]; then
    warn "nginx root ${root} does not exist; skip permission probe"
    return 0
  fi
  if sudo -u www-data test -x "${root}" 2>/dev/null &&
    sudo -u www-data test -r "${root}/index.html" 2>/dev/null; then
    return 0
  fi

  warn "www-data cannot read ${root}; granting traverse/read access"
  local dir="${root}"
  while [[ "${dir}" != "/" && -n "${dir}" ]]; do
    sudo setfacl -m u:www-data:x "${dir}" 2>/dev/null || sudo chmod o+x "${dir}" 2>/dev/null || true
    dir="$(dirname "${dir}")"
  done
  sudo setfacl -R -m u:www-data:rX "${root}" 2>/dev/null || sudo chmod -R o+rX "${root}" 2>/dev/null || true

  if sudo -u www-data test -r "${root}/index.html" 2>/dev/null; then
    log "nginx can read ${root}"
  else
    warn "nginx still cannot read ${root}; check the path permissions manually"
  fi
}

http_check() {
  local name="$1"
  local url="$2"
  if curl -fsS --max-time 5 "${url}" >/dev/null; then
    printf 'ok     %-32s %s\n' "${name}" "${url}"
  else
    printf 'failed %-32s %s\n' "${name}" "${url}"
    return 1
  fi
}

# Optional runtime: print pending (not failed) so status-all does not look red.
http_check_optional() {
  local name="$1"
  local url="$2"
  if curl -fsS --max-time 5 "${url}" >/dev/null; then
    printf 'ok     %-32s %s\n' "${name}" "${url}"
  else
    printf 'pending %-32s %s\n' "${name}" "${url}"
    return 1
  fi
}

service_status_line() {
  local service_name="$1"
  if systemctl is-active --quiet "${service_name}"; then
    printf 'active %-36s\n' "${service_name}"
  else
    printf 'down   %-36s\n' "${service_name}"
    return 1
  fi
}

target_ports() {
  printf '%s\n' \
    "${PROJECT5_FRONTEND_PORT:-5173}" \
    "${PROJECT5_BACKEND_PORT:-5800}" \
    "${TOPIC3_BENCHMARK_PORT:-6006}" \
    "${TOPIC3_COMPLIANCE_PORT:-6311}" \
    "${TOPIC1_FRONTEND_PORT:-6101}" \
    "${TOPIC1_BACKEND_PORT:-6102}" \
    "${TOPIC2_SHOWCASE_PORT:-6201}" \
    "${TOPIC2_FILTERGUARD_PORT:-6211}" \
    "${TOPIC2_DYNBENCH_PORT:-8766}" \
    "${TOPIC3_DIVERSITY_UI_PORT:-6321}" \
    "${TOPIC3_DIVERSITY_API_PORT:-6322}" \
    "${TOPIC3_DIVERSITY_DATA_PORT:-6323}" \
    "${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_PORT:-8877}" \
    "${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_V2_PORT:-8878}" \
    "${TOPIC3_DIFFICULTY_PORT:-6331}" \
    "${TOPIC3_DIFFICULTY_ROUTER_PORT:-6332}" \
    "${TOPIC3_DIFFICULTY_GENERATION_WORKER_PORT:-6333}" \
    "${TOPIC3_DIFFICULTY_GUARD_WORKER_PORT:-6334}" \
    "${TOPIC3_RISK_AGENT_PORT:-6351}" \
    "${TOPIC3_RISK_QWEN_PORT:-6352}"
}

public_ports() {
  printf '%s\n' \
    "${PROJECT5_FRONTEND_PORT:-5173}" \
    "${PROJECT5_BACKEND_PORT:-5800}" \
    "${TOPIC3_BENCHMARK_PORT:-6006}" \
    "${TOPIC3_COMPLIANCE_PORT:-6311}" \
    "${TOPIC1_FRONTEND_PORT:-6101}" \
    "${TOPIC1_BACKEND_PORT:-6102}" \
    "${TOPIC2_SHOWCASE_PORT:-6201}" \
    "${TOPIC2_FILTERGUARD_PORT:-6211}" \
    "${TOPIC2_DYNBENCH_PORT:-8766}" \
    "${TOPIC3_DIVERSITY_UI_PORT:-6321}" \
    "${TOPIC3_DIVERSITY_API_PORT:-6322}" \
    "${TOPIC3_DIVERSITY_DATA_PORT:-6323}"
}
