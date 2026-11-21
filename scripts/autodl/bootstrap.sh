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
  config      Print resolved AutoDL deployment configuration.
  prepare     Create the persistent AutoDL directory layout.
  check       Check required baseline commands without changing services.
  install-project5
              Clone/update Project 5, install dependencies, and build frontend.
  install-topic1
              Clone/update Topic 1 repos, install backend and value QA deps,
              and build the Topic 1 frontend.
  install-topic2
              Clone/update Topic 2 repos and install Python packages.
  install-topic3-light
              Clone/update non-vLLM Topic 3 repos and install Python packages.
  install-light
              Install Project 5 plus Topic 1, Topic 2, and non-vLLM Topic 3.

This bootstrap path is safe for AutoDL no-GPU mode. It does not start GPU
workers and does not edit systemd or scripts/server.
USAGE
}

require_baseline_install_tools() {
  require_cmd git
  require_cmd node
  require_cmd npm
  require_cmd pnpm
  require_cmd rsync
  resolve_conda >/dev/null
  ensure_base_dirs
}

install_project5() {
  require_baseline_install_tools
  repo_update "${PROJECT5_REPO_NAME}" "${PROJECT5_REPO_URL}" "${PROJECT5_DIR}"
  ensure_conda_env "${CONDA_ENV}" "3.10"

  log "installing Project 5 backend dependencies"
  run_in_conda python -m pip install --upgrade pip
  run_in_conda python -m pip install -r "${PROJECT5_DIR}/web/backend/requirements.txt"

  log "installing Project 5 frontend dependencies and building"
  (
    cd "${PROJECT5_DIR}/web/frontend"
    pnpm install --frozen-lockfile || pnpm install
    VITE_API_BASE_URL="/api" \
    VITE_INTEGRATION_HOST="127.0.0.1" \
    VITE_TOPIC3_BENCHMARK_URL="/integration/topic3-benchmark/" \
    pnpm build
  )

  log "publishing Project 5 frontend dist to ${PROJECT5_FRONTEND_ROOT}"
  mkdir -p "${PROJECT5_FRONTEND_ROOT}"
  rsync -a --delete "${PROJECT5_DIR}/web/frontend/dist/" "${PROJECT5_FRONTEND_ROOT}/"
  log "Project 5 install complete"
}

install_topic1() {
  require_baseline_install_tools
  repo_update "${TOPIC1_REPO_NAME}" "${TOPIC1_REPO_URL}" "${TOPIC1_DIR}"
  repo_update "${TOPIC1_VALUE_QA_REPO_NAME}" "${TOPIC1_VALUE_QA_REPO_URL}" "${TOPIC1_VALUE_QA_DIR}"
  ensure_conda_env "${CONDA_ENV}" "3.10"

  log "installing Topic 1 backend dependencies"
  run_in_conda python -m pip install --upgrade pip
  run_in_conda python -m pip install -r "${TOPIC1_DIR}/backend/requirements.txt"

  log "installing Topic 1 value QA CLI dependencies"
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

  log "installing Topic 1 frontend dependencies and building"
  (
    cd "${TOPIC1_DIR}/frontend"
    npm install
    VITE_APP_RUNTIME_MODE=integration \
    VITE_UI_PORT="${TOPIC1_FRONTEND_PORT:-6101}" \
    VITE_API_PROXY_TARGET="http://127.0.0.1:${TOPIC1_BACKEND_PORT:-6102}" \
    VITE_WS_PROXY_TARGET="ws://127.0.0.1:${TOPIC1_BACKEND_PORT:-6102}" \
    npm run build
  )
  log "Topic 1 install complete"
}

install_topic2() {
  require_baseline_install_tools
  repo_update "${TOPIC2_FLYWHEEL_REPO_NAME}" "${TOPIC2_FLYWHEEL_REPO_URL}" "${TOPIC2_FLYWHEEL_DIR}"
  repo_update "${TOPIC2_FILTERGUARD_REPO_NAME}" "${TOPIC2_FILTERGUARD_REPO_URL}" "${TOPIC2_FILTERGUARD_DIR}"
  ensure_conda_env "${CONDA_ENV}" "3.10"

  log "installing Topic 2 DynBench"
  run_in_conda python -m pip install --upgrade pip
  run_in_conda python -m pip install -e "${TOPIC2_FLYWHEEL_DIR}"

  log "installing Topic 2 FilterGuard"
  run_in_conda python -m pip install -e "${TOPIC2_FILTERGUARD_DIR}"
  log "Topic 2 install complete"
}

ensure_json_server() {
  if command -v json-server >/dev/null 2>&1; then
    return
  fi
  require_cmd npm
  log "installing json-server globally"
  npm install -g json-server
}

install_topic3_light() {
  require_baseline_install_tools
  repo_update "${TOPIC3_BENCHMARK_REPO_NAME}" "${TOPIC3_BENCHMARK_REPO_URL}" "${TOPIC3_BENCHMARK_DIR}"
  repo_update "${TOPIC3_CULTURAL_GEN_REPO_NAME}" "${TOPIC3_CULTURAL_GEN_REPO_URL}" "${TOPIC3_CULTURAL_GEN_DIR}"
  ensure_conda_env "${CONDA_ENV}" "3.10"

  log "installing Topic 3 Benchmark dependencies"
  run_in_conda python -m pip install --upgrade pip
  run_in_conda python -m pip install -r "${TOPIC3_BENCHMARK_DIR}/requirements.txt"

  log "installing Topic 3 cultural diversity dependencies"
  run_in_conda python -m pip install -r "${TOPIC3_CULTURAL_GEN_DIR}/requirements.txt"
  ensure_json_server
  log "Topic 3 light install complete"
}

install_light() {
  install_project5
  install_topic1
  install_topic2
  install_topic3_light
  log "light install complete; GPU vLLM workers are still untouched"
}

command="${1:-}"
case "${command}" in
  config)
    print_config_summary
    ;;
  prepare)
    ensure_base_dirs
    log "prepared AutoDL directories under ${DEPLOY_ROOT}"
    ;;
  check)
    require_cmd git
    require_cmd node
    require_cmd npm
    require_cmd pnpm
    require_cmd rsync
    require_cmd curl
    resolve_conda >/dev/null
    log "baseline command check passed"
    ;;
  install-project5)
    install_project5
    ;;
  install-topic1)
    install_topic1
    ;;
  install-topic2)
    install_topic2
    ;;
  install-topic3-light)
    install_topic3_light
    ;;
  install-light)
    install_light
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    usage >&2
    die "unknown command: ${command}"
    ;;
esac
