#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

usage() {
  cat <<'USAGE'
Usage: bash scripts/server/deploy-all.sh [options]

Options:
  --config=PATH    Deploy env file (default: scripts/server/deploy.env)
  --dry-run        Print every mutating command (sudo/systemctl/git/pip/build)
                   without executing it. Config and systemd units are still read.
  --dump-config    Print the resolved KEY=value config and exit. Read-only; use
                   it to prove a change does not alter how a host resolves.
  --only=LIST      Deploy only these components (comma/space separated),
                   e.g. --only=project5,topic3-benchmark. Default: all.
  --tolerate       Continue after a failing component and report it at the end
                   (DEPLOY_STRICT=false). Default: abort on first failure.
  --strict         Abort on first failure (default).
  -h, --help       Show this help.

Components:
  project5, topic1, topic1-value-qa, topic2-dynbench, topic2-filterguard,
  topic2-showcase, topic3-benchmark, topic3-cultural-gen,
  topic3-cultural-corpus, topic3-cultural-assessment, topic3-compliance,
  topic3-difficulty, topic3-risk

The same knobs can be set in deploy.env: DEPLOY_COMPONENTS, DEPLOY_STRICT,
DEPLOY_DRY_RUN. Command line options win.
USAGE
}

DEPLOY_CONFIG="${SERVER_DIR}/deploy.env"
DUMP_CONFIG=false

while (($# > 0)); do
  case "$1" in
    --config)
      (($# >= 2)) || die "--config needs a value"
      DEPLOY_CONFIG="$2"
      shift
      ;;
    --config=*)
      DEPLOY_CONFIG="${1#*=}"
      ;;
    --dry-run)
      DEPLOY_DRY_RUN=true
      ;;
    --dump-config)
      DUMP_CONFIG=true
      ;;
    --only)
      (($# >= 2)) || die "--only needs a value"
      DEPLOY_COMPONENTS="$2"
      shift
      ;;
    --only=*)
      DEPLOY_COMPONENTS="${1#*=}"
      ;;
    --tolerate)
      DEPLOY_STRICT=false
      ;;
    --strict)
      DEPLOY_STRICT=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1 (see --help)"
      ;;
  esac
  shift
done

load_config "${DEPLOY_CONFIG}"

if bool_true "${DUMP_CONFIG}"; then
  dump_config
  exit 0
fi

require_cmd git
require_cmd node
require_cmd npm
require_cmd pnpm
require_cmd rsync
require_cmd sudo
require_cmd systemctl
require_cmd nginx
require_cmd json-server

if is_dry_run; then
  log "dry-run: no command will touch this host"
fi
validate_config "${DEPLOY_CONFIG}"

if deploy_strict; then
  log "deploy mode: strict (abort on first failure)"
else
  log "deploy mode: tolerate (record failures and continue)"
fi
if ! component_enabled all; then
  log "deploy components: ${DEPLOY_COMPONENTS}"
fi

systemd_env_value() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//%/%%}"
  printf '%s' "${value}"
}

component_step() {
  local component="$1"
  local label="$2"
  shift 2
  if ! component_enabled "${component}"; then
    log "skip [${component}] ${label}"
    return 0
  fi
  protected "${label}" "$@"
}

build_project5_frontend() {
  if is_dry_run; then
    log "[dry-run] (cd ${PROJECT5_DIR}/web/frontend && pnpm install && pnpm build)"
    return 0
  fi
  (
    cd "${PROJECT5_DIR}/web/frontend"
    pnpm install --frozen-lockfile || pnpm install
    VITE_API_BASE_URL="/api" \
    VITE_INTEGRATION_HOST="${PUBLIC_HOST}" \
    VITE_TOPIC3_BENCHMARK_URL="http://${PUBLIC_HOST}:${TOPIC3_BENCHMARK_PORT:-6006}" \
      pnpm build
  )
}

publish_project5_frontend() {
  sudo mkdir -p "${PROJECT5_FRONTEND_ROOT}"
  sudo rsync -a --delete "${PROJECT5_DIR}/web/frontend/dist/" \
    "${PROJECT5_FRONTEND_ROOT}/"
  ensure_nginx_can_read "${PROJECT5_FRONTEND_ROOT}"
}

install_project5_value_qa_cli() {
  if is_dry_run; then
    log "[dry-run] (cd ${TOPIC1_VALUE_QA_DIR} && python3 -m venv .venv && pip install -e .)"
    return 0
  fi
  (
    cd "${TOPIC1_VALUE_QA_DIR}"
    if [[ ! -x ".venv/bin/python" ]]; then
      python3 -m venv .venv
    fi
    . .venv/bin/activate
    python -m pip install --upgrade pip
    python -m pip install -e .
    python -m benchmark.cli list-skills | grep -q "value_qa"
  )
}

build_topic1_frontend() {
  if is_dry_run; then
    log "[dry-run] (cd ${TOPIC1_DIR}/frontend && npm install && npm run build)"
    return 0
  fi
  (
    cd "${TOPIC1_DIR}/frontend"
    npm install
    VITE_APP_RUNTIME_MODE=integration \
    VITE_API_BASE_URL="http://${PUBLIC_HOST}:${TOPIC1_BACKEND_PORT:-6102}" \
    VITE_WS_BASE_URL="ws://${PUBLIC_HOST}:${TOPIC1_BACKEND_PORT:-6102}" \
      npm run build
  )
}

sync_project5_backend_deploy_env() {
  local dropin_dirs=(
    "/etc/systemd/system/llmsafe-project5-backend.service.d"
    "/etc/systemd/system/llmsafe-project5-governance-worker.service.d"
  )
  local dropin_dir
  local dropin_path
  local legacy_proxy_dropin_path
  local benchmark_base_url="${BENCHMARK_BASE_URL:-http://127.0.0.1:${TOPIC3_BENCHMARK_PORT:-6006}}"
  local cultural_assessment_root="${CULTURAL_ASSESSMENT_ROOT:-${TOPIC3_CULTURAL_ASSESSMENT_DIR}}"
  local cultural_assessment_console_base_url="${CULTURAL_ASSESSMENT_CONSOLE_BASE_URL:-http://127.0.0.1:${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_PORT:-8877}}"
  local cultural_assessment_console_v2_base_url="${CULTURAL_ASSESSMENT_CONSOLE_V2_BASE_URL:-http://127.0.0.1:${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_V2_PORT:-8878}}"
  local cultural_corpus_generator_base_url="${CULTURAL_CORPUS_GENERATOR_BASE_URL:-}"
  local cultural_corpus_generator_root="${CULTURAL_CORPUS_GENERATOR_ROOT:-${TOPIC3_CULTURAL_CORPUS_DIR}/framework}"
  local cultural_corpus_runs_dir="${CULTURAL_CORPUS_RUNS_DIR:-${cultural_corpus_generator_root}/runs}"
  local compliance_edit_base_url="${COMPLIANCE_EDIT_BASE_URL:-http://127.0.0.1:${TOPIC3_COMPLIANCE_PORT:-6311}}"
  local compliance_edit_timeout_seconds="${COMPLIANCE_EDIT_TIMEOUT_SECONDS:-300}"
  local proxy_url="${PROJECT5_BACKEND_PROXY_URL:-}"
  local no_proxy="${PROJECT5_BACKEND_NO_PROXY:-127.0.0.1,localhost,platform.example.invalid,proxy.example.invalid}"

  log "Project 5 backend Benchmark upstream: ${benchmark_base_url}"
  log "Project 5 cultural corpus runs dir: ${cultural_corpus_runs_dir}"

  for dropin_dir in "${dropin_dirs[@]}"; do
    dropin_path="${dropin_dir}/10-deploy-env.conf"
    legacy_proxy_dropin_path="${dropin_dir}/10-proxy.conf"
    sudo mkdir -p "${dropin_dir}"
    sudo tee "${dropin_path}" >/dev/null <<SYSTEMD
[Service]
Environment="BENCHMARK_BASE_URL=$(systemd_env_value "${benchmark_base_url}")"
Environment="CULTURAL_ASSESSMENT_ROOT=$(systemd_env_value "${cultural_assessment_root}")"
Environment="CULTURAL_ASSESSMENT_CONSOLE_BASE_URL=$(systemd_env_value "${cultural_assessment_console_base_url}")"
Environment="CULTURAL_ASSESSMENT_CONSOLE_V2_BASE_URL=$(systemd_env_value "${cultural_assessment_console_v2_base_url}")"
Environment="CULTURAL_CORPUS_GENERATOR_BASE_URL=$(systemd_env_value "${cultural_corpus_generator_base_url}")"
Environment="CULTURAL_CORPUS_GENERATOR_ROOT=$(systemd_env_value "${cultural_corpus_generator_root}")"
Environment="CULTURAL_CORPUS_RUNS_DIR=$(systemd_env_value "${cultural_corpus_runs_dir}")"
Environment="COMPLIANCE_EDIT_BASE_URL=$(systemd_env_value "${compliance_edit_base_url}")"
Environment="COMPLIANCE_EDIT_TIMEOUT_SECONDS=$(systemd_env_value "${compliance_edit_timeout_seconds}")"
Environment="TOPIC3_RISK_AGENT_URL=$(systemd_env_value "${TOPIC3_RISK_AGENT_URL}")"
Environment="TOPIC3_RISK_QWEN_API_BASE=$(systemd_env_value "${TOPIC3_RISK_QWEN_API_BASE}")"
Environment="TOPIC3_RISK_BENCHMARK_PROJECT_ROOT=$(systemd_env_value "${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}")"
Environment="TOPIC3_RISK_BENCHMARK_PYTHON=$(systemd_env_value "${TOPIC3_RISK_BENCHMARK_PYTHON}")"
SYSTEMD

    if [[ -n "${proxy_url}" ]]; then
      sudo tee -a "${dropin_path}" >/dev/null <<SYSTEMD
Environment="HTTP_PROXY=$(systemd_env_value "${proxy_url}")"
Environment="HTTPS_PROXY=$(systemd_env_value "${proxy_url}")"
Environment="http_proxy=$(systemd_env_value "${proxy_url}")"
Environment="https_proxy=$(systemd_env_value "${proxy_url}")"
Environment="NO_PROXY=$(systemd_env_value "${no_proxy}")"
Environment="no_proxy=$(systemd_env_value "${no_proxy}")"
SYSTEMD
    fi

    sudo rm -f "${legacy_proxy_dropin_path}"
  done

  if [[ -n "${proxy_url}" ]]; then
    log "Project 5 backend/governance-worker proxy enabled via PROJECT5_BACKEND_PROXY_URL"
  else
    log "Project 5 backend/governance-worker proxy disabled"
  fi
}

service_component() {
  case "$1" in
    llmsafe-project5-topic2-showcase) printf 'topic2-showcase' ;;
    llmsafe-project5-*) printf 'project5' ;;
    llmsafe-topic1-backend|llmsafe-topic1-frontend) printf 'topic1' ;;
    llmsafe-topic2-dynbench) printf 'topic2-dynbench' ;;
    llmsafe-topic2-filterguard) printf 'topic2-filterguard' ;;
    llmsafe-topic3-benchmark) printf 'topic3-benchmark' ;;
    llmsafe-topic3-compliance) printf 'topic3-compliance' ;;
    llmsafe-topic3-diversity-*) printf 'topic3-cultural-gen' ;;
    llmsafe-topic3-cultural-assessment-*) printf 'topic3-cultural-assessment' ;;
    llmsafe-topic3-difficulty-*) printf 'topic3-difficulty' ;;
    llmsafe-topic3-risk-agent) printf 'topic3-risk' ;;
    *) printf '' ;;
  esac
}

component_step project5 "write Project 5 systemd deploy-env" sync_project5_backend_deploy_env
component_step project5 "install Project 5 nginx site" install_project5_nginx_site
sudo systemctl disable --now llmsafe-project5-frontend 2>/dev/null || true

log "updating repositories"
component_step project5 "update Project 5" \
  repo_update "${PROJECT5_REPO_NAME}" "${PROJECT5_REPO_URL}" "${PROJECT5_DIR}"
component_step topic1 "update Topic 1" \
  repo_update "${TOPIC1_REPO_NAME}" "${TOPIC1_REPO_URL}" "${TOPIC1_DIR}"
component_step topic1-value-qa "update Topic 1 value_qa" \
  repo_update "${TOPIC1_VALUE_QA_REPO_NAME}" "${TOPIC1_VALUE_QA_REPO_URL}" "${TOPIC1_VALUE_QA_DIR}"
component_step topic2-dynbench "update Topic 2 DynBench" \
  repo_update "${TOPIC2_FLYWHEEL_REPO_NAME}" "${TOPIC2_FLYWHEEL_REPO_URL}" "${TOPIC2_FLYWHEEL_DIR}"
component_step topic2-filterguard "update Topic 2 FilterGuard" \
  repo_update "${TOPIC2_FILTERGUARD_REPO_NAME}" "${TOPIC2_FILTERGUARD_REPO_URL}" "${TOPIC2_FILTERGUARD_DIR}"
component_step topic3-benchmark "update Topic 3 Benchmark" \
  repo_update "${TOPIC3_BENCHMARK_REPO_NAME}" "${TOPIC3_BENCHMARK_REPO_URL}" "${TOPIC3_BENCHMARK_DIR}"
component_step topic3-cultural-gen "update Topic 3 cultural generation" \
  repo_update "${TOPIC3_CULTURAL_GEN_REPO_NAME}" "${TOPIC3_CULTURAL_GEN_REPO_URL}" "${TOPIC3_CULTURAL_GEN_DIR}"
component_step topic3-cultural-corpus "update Topic 3 cultural corpus" \
  repo_update "${TOPIC3_CULTURAL_CORPUS_REPO_NAME}" "${TOPIC3_CULTURAL_CORPUS_REPO_URL}" "${TOPIC3_CULTURAL_CORPUS_DIR}"
component_step topic3-cultural-assessment "update Topic 3 cultural assessment" \
  repo_update "${TOPIC3_CULTURAL_ASSESSMENT_REPO_NAME}" "${TOPIC3_CULTURAL_ASSESSMENT_REPO_URL}" "${TOPIC3_CULTURAL_ASSESSMENT_DIR}"
component_step topic3-compliance "update Topic 3 compliance editing" \
  repo_update "${TOPIC3_COMPLIANCE_REPO_NAME}" "${TOPIC3_COMPLIANCE_REPO_URL}" "${TOPIC3_COMPLIANCE_DIR}"
component_step topic3-difficulty "update Topic 3 dynamic difficulty" \
  repo_update "${TOPIC3_DIFFICULTY_REPO_NAME}" "${TOPIC3_DIFFICULTY_REPO_URL}" "${TOPIC3_DIFFICULTY_DIR}"
# Topic 3 dynamic risk is a local snapshot / offline generation package.
# Never clone or pull from GitHub during deploy.
component_step topic3-risk "check Topic 3 dynamic risk snapshot" \
  ensure_local_snapshot_repo "${TOPIC3_RISK_REPO_NAME}" "${TOPIC3_RISK_DIR}"

ensure_conda_env "${CONDA_ENV}" "3.10"
if component_enabled topic3-difficulty; then
  ensure_conda_env "${TOPIC3_DIFFICULTY_CONDA_ENV}" "${TOPIC3_DIFFICULTY_PYTHON:-3.12}"
  run_mutation mkdir -p "${TOPIC3_DIFFICULTY_HF_HOME}"
else
  log "skip [topic3-difficulty] create ${TOPIC3_DIFFICULTY_CONDA_ENV}"
fi

log "installing Project 5 backend dependencies"
if component_enabled project5; then
  protected "upgrade pip in ${CONDA_ENV}" run_in_conda python -m pip install --upgrade pip
  protected "install Project 5 backend requirements" \
    run_in_conda python -m pip install -r "${PROJECT5_DIR}/web/backend/requirements.txt"
fi

log "installing Project 5 frontend dependencies and building"
component_step project5 "build Project 5 frontend" build_project5_frontend

log "publishing Project 5 frontend dist to nginx root"
component_step project5 "publish Project 5 frontend" publish_project5_frontend

log "installing Topic 1 backend dependencies"
if component_enabled topic1; then
  protected "install Topic 1 backend requirements" \
    run_in_conda python -m pip install -r "${TOPIC1_DIR}/backend/requirements.txt"
fi

log "installing Topic 1 value_qa CLI dependencies"
component_step topic1-value-qa "install Topic 1 value_qa CLI" install_project5_value_qa_cli

log "installing Topic 1 frontend dependencies and building"
component_step topic1 "build Topic 1 frontend" build_topic1_frontend

log "installing Topic 2 DynBench"
if component_enabled topic2-dynbench; then
  protected "install Topic 2 DynBench" run_in_conda python -m pip install -e "${TOPIC2_FLYWHEEL_DIR}"
fi

log "installing Topic 2 FilterGuard"
if component_enabled topic2-filterguard; then
  protected "install Topic 2 FilterGuard" run_in_conda python -m pip install -e "${TOPIC2_FILTERGUARD_DIR}"
fi

log "installing Topic 3 Benchmark dependencies"
if component_enabled topic3-benchmark; then
  protected "install Topic 3 Benchmark requirements" \
    run_in_conda python -m pip install -r "${TOPIC3_BENCHMARK_DIR}/requirements.txt"
fi

log "installing Topic 3 compliance editing dependencies"
if component_enabled topic3-compliance; then
  if topic3_compliance_ready; then
    if is_dry_run; then
      log "[dry-run] $(resolve_uv) sync --project ${TOPIC3_COMPLIANCE_DIR}/editing_api --directory ${TOPIC3_COMPLIANCE_DIR}"
    else
      protected "uv sync Topic 3 compliance" \
        "$(resolve_uv)" sync --project "${TOPIC3_COMPLIANCE_DIR}/editing_api" --directory "${TOPIC3_COMPLIANCE_DIR}"
    fi
  else
    warn "Topic 3 compliance repo missing at ${TOPIC3_COMPLIANCE_DIR}; skipping uv sync"
  fi
fi

log "installing Topic 3 cultural diversity dependencies"
if component_enabled topic3-cultural-gen; then
  protected "install Topic 3 cultural generation requirements" \
    run_in_conda python -m pip install -r "${TOPIC3_CULTURAL_GEN_DIR}/requirements.txt"
fi

log "installing Topic 3 dynamic difficulty dependencies"
if component_enabled topic3-difficulty; then
  protected "upgrade pip in ${TOPIC3_DIFFICULTY_CONDA_ENV}" \
    run_mutation "$(resolve_conda)" run -n "${TOPIC3_DIFFICULTY_CONDA_ENV}" python -m pip install --upgrade pip
  protected "install Topic 3 difficulty vllm_router" \
    run_mutation "$(resolve_conda)" run -n "${TOPIC3_DIFFICULTY_CONDA_ENV}" python -m pip install -e "${TOPIC3_DIFFICULTY_DIR}/vllm_router"
fi

if topic3_risk_snapshot_ready; then
  if component_enabled topic3-risk; then
    log "installing Topic 3 dynamic risk Agent dependencies"
    ensure_conda_env "${TOPIC3_RISK_CONDA_ENV}" "3.10"
    protected "upgrade pip in ${TOPIC3_RISK_CONDA_ENV}" \
      run_mutation "$(resolve_conda)" run -n "${TOPIC3_RISK_CONDA_ENV}" python -m pip install --upgrade pip
    protected "install Topic 3 risk Agent requirements" \
      run_mutation "$(resolve_conda)" run -n "${TOPIC3_RISK_CONDA_ENV}" python -m pip install -r \
        "${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}/qwen_agent_server/requirements.txt"
  fi
else
  warn "topic3-risk snapshot missing; skip Agent conda env and pip install"
fi

if component_enabled topic3-risk; then
  install_topic3_risk_agent_unit
fi

log "restarting services"
sudo systemctl daemon-reload
if component_enabled project5; then
  install_project5_governance_worker_unit
fi
if component_enabled topic3-risk; then
  enable_topic3_risk_agent
fi
if component_enabled project5; then
  enable_project5_governance_worker
fi
services=(
  llmsafe-topic3-benchmark
  llmsafe-topic3-compliance
  llmsafe-topic3-diversity-data
  llmsafe-topic3-diversity-backend
  llmsafe-topic3-diversity-frontend
  llmsafe-topic3-cultural-assessment-console
  llmsafe-topic3-cultural-assessment-console-v2
  llmsafe-topic3-difficulty-agent
  llmsafe-topic2-dynbench
  llmsafe-topic2-filterguard
  llmsafe-topic1-backend
  llmsafe-topic1-frontend
  llmsafe-project5-backend
  llmsafe-project5-topic2-showcase
)

if project5_governance_worker_enabled; then
  services=(
    llmsafe-project5-governance-worker
    "${services[@]}"
  )
else
  log "Project 5 governance worker disabled: stopping llmsafe-project5-governance-worker"
  sudo systemctl disable --now llmsafe-project5-governance-worker 2>/dev/null || true
fi

if topic3_difficulty_starts_local_inference; then
  sudo systemctl enable \
    llmsafe-topic3-difficulty-generation-worker \
    llmsafe-topic3-difficulty-guard-worker \
    llmsafe-topic3-difficulty-router
  services=(
    llmsafe-topic3-difficulty-generation-worker
    llmsafe-topic3-difficulty-guard-worker
    llmsafe-topic3-difficulty-router
    "${services[@]}"
  )
else
  log "Topic 3 difficulty local inference disabled: stopping local 176 router/workers"
  sudo systemctl disable --now \
    llmsafe-topic3-difficulty-generation-worker \
    llmsafe-topic3-difficulty-guard-worker \
    llmsafe-topic3-difficulty-router 2>/dev/null || true
fi

if topic3_risk_snapshot_ready; then
  services=(
    llmsafe-topic3-risk-agent
    "${services[@]}"
  )
fi

for service in "${services[@]}"; do
  service_scope="$(service_component "${service}")"
  if [[ -n "${service_scope}" ]] && ! component_enabled "${service_scope}"; then
    log "skip [${service_scope}] restart ${service}"
    continue
  fi
  protected "restart ${service}" sudo systemctl restart "${service}"
done
sudo systemctl reload nginx || sudo systemctl restart nginx

log "deployment complete; running status checks"
if is_dry_run; then
  log "[dry-run] skip status-all.sh (it queries live services)"
elif ! "${SERVER_DIR}/status-all.sh"; then
  warn "status checks failed; GPU workers may still be warming up, downloading models, or the external router tunnel may be down"
fi
