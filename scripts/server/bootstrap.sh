#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

load_config "${SERVER_DIR}/deploy.env"
validate_config "${SERVER_DIR}/deploy.env"

require_cmd sudo
require_cmd systemctl
require_cmd node
require_cmd npm
require_cmd pnpm
require_cmd nginx
require_cmd json-server

CONDA_BIN_RESOLVED="$(resolve_conda)"
PROJECT5_CORS_ORIGINS_DEFAULT='["http://localhost:5173","http://127.0.0.1:5173"]'
PROJECT5_CORS_ORIGINS_RESOLVED="${PROJECT5_CORS_ORIGINS:-${PROJECT5_CORS_ORIGINS_DEFAULT}}"
PROJECT5_CORS_ORIGINS_SYSTEMD="${PROJECT5_CORS_ORIGINS_RESOLVED//\"/\\\"}"
TOPIC3_DIFFICULTY_MODEL_MAP_RESOLVED="{\"${TOPIC3_DIFFICULTY_GENERATION_MODEL_NAME:-Qwen3.5-9B}\":\"http://127.0.0.1:${TOPIC3_DIFFICULTY_GENERATION_WORKER_PORT:-6333}/v1\",\"${TOPIC3_DIFFICULTY_GUARD_MODEL_NAME:-Qwen3Guard-Gen-4B}\":\"http://127.0.0.1:${TOPIC3_DIFFICULTY_GUARD_WORKER_PORT:-6334}/v1\"}"
TOPIC3_DIFFICULTY_MODEL_MAP_SYSTEMD="${TOPIC3_DIFFICULTY_MODEL_MAP_RESOLVED//\"/\\\"}"
TOPIC3_DIFFICULTY_AGENT_AFTER="network.target"
if topic3_difficulty_starts_local_inference; then
  TOPIC3_DIFFICULTY_AGENT_AFTER="network.target llmsafe-topic3-difficulty-router.service"
fi
TOPIC1_LLM_PROVIDER_ENV=""
if [[ -n "${TOPIC1_LLM_PROVIDER:-}" ]]; then
  TOPIC1_LLM_PROVIDER_ENV="Environment=LLM_PROVIDER=${TOPIC1_LLM_PROVIDER}"
fi

log "creating deployment directories"
sudo mkdir -p "${REPOS_DIR}" "${WWW_DIR}" "${LOG_DIR}" "${PROJECT5_FRONTEND_ROOT}" "${TOPIC3_DIFFICULTY_HF_HOME}"
sudo chown -R "$(id -u):$(id -g)" "${DEPLOY_ROOT}"

ensure_conda_env "${CONDA_ENV}" "3.10"
ensure_conda_env "${TOPIC3_DIFFICULTY_CONDA_ENV}" "${TOPIC3_DIFFICULTY_PYTHON:-3.12}"
if topic3_risk_snapshot_ready; then
  ensure_conda_env "${TOPIC3_RISK_CONDA_ENV}" "3.10"
fi

log "installing systemd units"

install_systemd_unit "llmsafe-project5-backend" "[Unit]
Description=LLMSafe Project 5 backend
After=network.target llmsafe-topic3-benchmark.service llmsafe-topic1-backend.service llmsafe-topic3-diversity-backend.service llmsafe-topic3-cultural-assessment-console.service llmsafe-topic3-cultural-assessment-console-v2.service llmsafe-topic3-difficulty-agent.service

[Service]
Type=simple
WorkingDirectory=${PROJECT5_DIR}/web/backend
Environment=PYTHONPATH=.
Environment=\"CORS_ORIGINS=${PROJECT5_CORS_ORIGINS_SYSTEMD}\"
Environment=BENCHMARK_BASE_URL=${BENCHMARK_BASE_URL:-http://127.0.0.1:6006}
Environment=TOPIC1_PROJECT1_BASE_URL=${TOPIC1_PROJECT1_BASE_URL:-http://127.0.0.1:6102}
Environment=TOPIC4_INPUT_WORKFLOW_BASE_URL=${TOPIC4_INPUT_WORKFLOW_BASE_URL:-http://127.0.0.1:8081}
Environment=CULTURAL_GEN_BASE_URL=${CULTURAL_GEN_BASE_URL:-http://127.0.0.1:6322}
Environment=CULTURAL_GEN_DATA_BASE_URL=${CULTURAL_GEN_DATA_BASE_URL:-http://127.0.0.1:6323}
Environment=CULTURAL_ASSESSMENT_ROOT=${CULTURAL_ASSESSMENT_ROOT}
Environment=CULTURAL_ASSESSMENT_CONSOLE_BASE_URL=${CULTURAL_ASSESSMENT_CONSOLE_BASE_URL}
Environment=CULTURAL_ASSESSMENT_CONSOLE_V2_BASE_URL=${CULTURAL_ASSESSMENT_CONSOLE_V2_BASE_URL}
Environment=CULTURAL_CORPUS_GENERATOR_BASE_URL=${CULTURAL_CORPUS_GENERATOR_BASE_URL:-}
Environment=CULTURAL_CORPUS_GENERATOR_ROOT=${CULTURAL_CORPUS_GENERATOR_ROOT}
Environment=CULTURAL_CORPUS_RUNS_DIR=${CULTURAL_CORPUS_RUNS_DIR}
Environment=COMPLIANCE_EDIT_BASE_URL=${COMPLIANCE_EDIT_BASE_URL}
Environment=COMPLIANCE_EDIT_TIMEOUT_SECONDS=${COMPLIANCE_EDIT_TIMEOUT_SECONDS}
Environment=TOPIC3_DIFFICULTY_BASE_URL=${TOPIC3_DIFFICULTY_BASE_URL:-http://127.0.0.1:6331}
Environment=TOPIC3_DIFFICULTY_VLLM_API_BASE=${TOPIC3_DIFFICULTY_VLLM_API_BASE:-http://127.0.0.1:6332/v1}
Environment=TOPIC3_RISK_AGENT_URL=${TOPIC3_RISK_AGENT_URL:-http://127.0.0.1:6351/chat}
Environment=TOPIC3_RISK_QWEN_API_BASE=${TOPIC3_RISK_QWEN_API_BASE}
Environment=TOPIC3_RISK_BENCHMARK_PROJECT_ROOT=${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}
Environment=TOPIC3_RISK_BENCHMARK_PYTHON=${TOPIC3_RISK_BENCHMARK_PYTHON:-}
Environment=TOPIC2_FILTERGUARD_BASE_URL=${TOPIC2_FILTERGUARD_BASE_URL:-http://127.0.0.1:${TOPIC2_FILTERGUARD_PORT:-6211}}
Environment=TOPIC2_FILTERGUARD_METHOD=${TOPIC2_FILTERGUARD_METHOD:-keyword}
Environment=TOPIC2_FILTERGUARD_TIMEOUT_SECONDS=${TOPIC2_FILTERGUARD_TIMEOUT_SECONDS:-10}
Environment=TOPIC1_VALUE_QA_PROJECT_ROOT=${TOPIC1_VALUE_QA_PROJECT_ROOT}
Environment=TOPIC1_VALUE_QA_PYTHON=${TOPIC1_VALUE_QA_PYTHON}
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${CONDA_ENV} python -m uvicorn app.main:app --host 0.0.0.0 --port ${PROJECT5_BACKEND_PORT:-5800}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-project5-topic2-showcase" "[Unit]
Description=LLMSafe Topic 2 showcase
After=network.target llmsafe-topic2-dynbench.service

[Service]
Type=simple
WorkingDirectory=${PROJECT5_DIR}/web/backend
Environment=PYTHONPATH=.
Environment=TOPIC2_SHOWCASE_ASSET_ROOT=${TOPIC2_SHOWCASE_ASSET_ROOT:-${PROJECT5_DIR}/web/backend/topic2-showcase-assets}
Environment=TOPIC2_SHOWCASE_DYNBENCH_BASE_URL=${TOPIC2_SHOWCASE_DYNBENCH_BASE_URL:-http://127.0.0.1:8766}
Environment=TOPIC2_SHOWCASE_DYNBENCH_PUBLIC_BASE_URL=${TOPIC2_SHOWCASE_DYNBENCH_PUBLIC_BASE_URL:-http://${PUBLIC_HOST}:${TOPIC2_DYNBENCH_PORT:-8766}}
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${CONDA_ENV} python -m uvicorn app.topic2_showcase.main:app --host 0.0.0.0 --port ${TOPIC2_SHOWCASE_PORT:-6201}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic1-backend" "[Unit]
Description=LLMSafe Topic 1 indicator backend
After=network.target

[Service]
Type=simple
WorkingDirectory=${TOPIC1_DIR}/backend
Environment=APP_RUNTIME_MODE=integration
Environment=APP_HOST=0.0.0.0
Environment=APP_PORT=${TOPIC1_BACKEND_PORT:-6102}
Environment=DEBUG=false
Environment=POLICY_CRAWL_ENABLED=${TOPIC1_POLICY_CRAWL_ENABLED:-false}
${TOPIC1_LLM_PROVIDER_ENV}
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${CONDA_ENV} python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic1-frontend" "[Unit]
Description=LLMSafe Topic 1 frontend preview
After=network.target llmsafe-topic1-backend.service

[Service]
Type=simple
WorkingDirectory=${TOPIC1_DIR}/frontend
Environment=VITE_APP_RUNTIME_MODE=integration
Environment=VITE_API_BASE_URL=http://${PUBLIC_HOST}:${TOPIC1_BACKEND_PORT:-6102}
Environment=VITE_WS_BASE_URL=ws://${PUBLIC_HOST}:${TOPIC1_BACKEND_PORT:-6102}
ExecStart=/usr/bin/npm run preview -- --host 0.0.0.0 --port ${TOPIC1_FRONTEND_PORT:-6101}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic2-dynbench" "[Unit]
Description=LLMSafe Topic 2 DynBench WebUI
After=network.target

[Service]
Type=simple
WorkingDirectory=${TOPIC2_FLYWHEEL_DIR}
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${CONDA_ENV} autobench-web --host 0.0.0.0 --port ${TOPIC2_DYNBENCH_PORT:-8766}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic2-filterguard" "[Unit]
Description=LLMSafe Topic 2 FilterGuard keyword API
After=network.target

[Service]
Type=simple
WorkingDirectory=${TOPIC2_FILTERGUARD_DIR}
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${CONDA_ENV} filterguard serve --methods keyword --host 0.0.0.0 --port ${TOPIC2_FILTERGUARD_PORT:-6211}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic3-benchmark" "[Unit]
Description=LLMSafe Topic 3 risk benchmark
After=network.target

[Service]
Type=simple
WorkingDirectory=${TOPIC3_BENCHMARK_DIR}
Environment=PORT=${TOPIC3_BENCHMARK_PORT:-6006}
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${CONDA_ENV} python -m uvicorn app:app --host 0.0.0.0 --port ${TOPIC3_BENCHMARK_PORT:-6006}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic3-diversity-data" "[Unit]
Description=LLMSafe Topic 3 cultural diversity data (json-server)
After=network.target

[Service]
Type=simple
WorkingDirectory=${TOPIC3_CULTURAL_GEN_DIR}
ExecStart=$(command -v json-server) --watch data/db.json --host 0.0.0.0 --port ${TOPIC3_DIVERSITY_DATA_PORT:-6323}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic3-diversity-backend" "[Unit]
Description=LLMSafe Topic 3 cultural diversity backend (FastAPI)
After=network.target llmsafe-topic3-diversity-data.service

[Service]
Type=simple
WorkingDirectory=${TOPIC3_CULTURAL_GEN_DIR}
Environment=APP_HOST=0.0.0.0
Environment=APP_PORT=${TOPIC3_DIVERSITY_API_PORT:-6322}
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${CONDA_ENV} python backend.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic3-diversity-frontend" "[Unit]
Description=LLMSafe Topic 3 cultural diversity frontend (static UI)
After=network.target llmsafe-topic3-diversity-backend.service

[Service]
Type=simple
WorkingDirectory=${TOPIC3_CULTURAL_GEN_DIR}
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${CONDA_ENV} python -m http.server ${TOPIC3_DIVERSITY_UI_PORT:-6321} --bind 0.0.0.0
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic3-cultural-assessment-console" "[Unit]
Description=LLMSafe Topic 3 cultural assessment console
After=network.target

[Service]
Type=simple
WorkingDirectory=${TOPIC3_CULTURAL_ASSESSMENT_DIR}
EnvironmentFile=-${TOPIC3_CULTURAL_ASSESSMENT_DIR}/.env
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${CONDA_ENV} python culture_eval_console/server.py --host 127.0.0.1 --port ${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_PORT:-8877}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic3-cultural-assessment-console-v2" "[Unit]
Description=LLMSafe Topic 3 cultural assessment console v2
After=network.target

[Service]
Type=simple
WorkingDirectory=${TOPIC3_CULTURAL_ASSESSMENT_DIR}
EnvironmentFile=-${TOPIC3_CULTURAL_ASSESSMENT_DIR}/.env
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${CONDA_ENV} python culture_eval_console_v2/server.py --host 127.0.0.1 --port ${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_V2_PORT:-8878}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic3-difficulty-generation-worker" "[Unit]
Description=LLMSafe Topic 3 dynamic difficulty generation worker
After=network.target

[Service]
Type=simple
WorkingDirectory=${TOPIC3_DIFFICULTY_DIR}
Environment=CUDA_VISIBLE_DEVICES=${TOPIC3_DIFFICULTY_GENERATION_GPU:-0}
Environment=HF_HOME=${TOPIC3_DIFFICULTY_HF_HOME}
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${TOPIC3_DIFFICULTY_CONDA_ENV} vllm serve ${TOPIC3_DIFFICULTY_GENERATION_MODEL_SOURCE:-Qwen/Qwen3.5-9B} --host 127.0.0.1 --port ${TOPIC3_DIFFICULTY_GENERATION_WORKER_PORT:-6333} --served-model-name ${TOPIC3_DIFFICULTY_GENERATION_MODEL_NAME:-Qwen3.5-9B}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic3-difficulty-guard-worker" "[Unit]
Description=LLMSafe Topic 3 dynamic difficulty guard worker
After=network.target

[Service]
Type=simple
WorkingDirectory=${TOPIC3_DIFFICULTY_DIR}
Environment=CUDA_VISIBLE_DEVICES=${TOPIC3_DIFFICULTY_GUARD_GPU:-1}
Environment=HF_HOME=${TOPIC3_DIFFICULTY_HF_HOME}
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${TOPIC3_DIFFICULTY_CONDA_ENV} vllm serve ${TOPIC3_DIFFICULTY_GUARD_MODEL_SOURCE:-Qwen/Qwen3Guard-Gen-4B} --host 127.0.0.1 --port ${TOPIC3_DIFFICULTY_GUARD_WORKER_PORT:-6334} --served-model-name ${TOPIC3_DIFFICULTY_GUARD_MODEL_NAME:-Qwen3Guard-Gen-4B}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic3-difficulty-router" "[Unit]
Description=LLMSafe Topic 3 dynamic difficulty vLLM router
After=network.target llmsafe-topic3-difficulty-generation-worker.service llmsafe-topic3-difficulty-guard-worker.service

[Service]
Type=simple
WorkingDirectory=${TOPIC3_DIFFICULTY_DIR}
Environment=\"VLLM_ROUTER_MODEL_MAP=${TOPIC3_DIFFICULTY_MODEL_MAP_SYSTEMD}\"
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${TOPIC3_DIFFICULTY_CONDA_ENV} python -m uvicorn main:app --app-dir vllm_router --host 127.0.0.1 --port ${TOPIC3_DIFFICULTY_ROUTER_PORT:-6332}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_systemd_unit "llmsafe-topic3-difficulty-agent" "[Unit]
Description=LLMSafe Topic 3 dynamic difficulty Agent UI and API
After=${TOPIC3_DIFFICULTY_AGENT_AFTER}

[Service]
Type=simple
WorkingDirectory=${TOPIC3_DIFFICULTY_DIR}
Environment=TOPIC3_DIFFICULTY_VLLM_API_BASE=${TOPIC3_DIFFICULTY_VLLM_API_BASE:-http://127.0.0.1:6332/v1}
ExecStart=${CONDA_BIN_RESOLVED} run --no-capture-output -n ${TOPIC3_DIFFICULTY_CONDA_ENV} python ui/server.py --host 127.0.0.1 --port ${TOPIC3_DIFFICULTY_PORT:-6331}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target"

install_topic3_risk_agent_unit
install_project5_governance_worker_unit

install_topic3_compliance_unit
install_project5_nginx_site
sudo systemctl disable --now llmsafe-project5-frontend 2>/dev/null || true
sudo systemctl enable nginx
sudo systemctl reload nginx || sudo systemctl restart nginx

sudo systemctl daemon-reload

# Only enable a unit once the directory it runs from exists. bootstrap runs
# before deploy-all.sh clones the Topic repos, so enabling unconditionally
# leaves units pointed at missing directories that restart-loop forever.
enable_ready_units() {
  local ready=()
  local service
  local path
  while (($# >= 2)); do
    service="$1"
    path="$2"
    shift 2
    if [[ -d "${path}" ]]; then
      ready+=("${service}")
    else
      warn "skip enable ${service}: ${path} missing (deploy-all.sh enables it after clone)"
    fi
  done
  if ((${#ready[@]} > 0)); then
    sudo systemctl enable "${ready[@]}"
  fi
}

enable_ready_units \
  llmsafe-project5-backend "${PROJECT5_DIR}" \
  llmsafe-project5-topic2-showcase "${PROJECT5_DIR}" \
  llmsafe-topic1-backend "${TOPIC1_DIR}" \
  llmsafe-topic1-frontend "${TOPIC1_DIR}" \
  llmsafe-topic2-dynbench "${TOPIC2_FLYWHEEL_DIR}" \
  llmsafe-topic2-filterguard "${TOPIC2_FILTERGUARD_DIR}" \
  llmsafe-topic3-benchmark "${TOPIC3_BENCHMARK_DIR}" \
  llmsafe-topic3-diversity-data "${TOPIC3_CULTURAL_GEN_DIR}" \
  llmsafe-topic3-diversity-backend "${TOPIC3_CULTURAL_GEN_DIR}" \
  llmsafe-topic3-diversity-frontend "${TOPIC3_CULTURAL_GEN_DIR}" \
  llmsafe-topic3-cultural-assessment-console "${TOPIC3_CULTURAL_ASSESSMENT_DIR}" \
  llmsafe-topic3-cultural-assessment-console-v2 "${TOPIC3_CULTURAL_ASSESSMENT_DIR}" \
  llmsafe-topic3-difficulty-agent "${TOPIC3_DIFFICULTY_DIR}"
enable_topic3_risk_agent
enable_topic3_compliance
enable_project5_governance_worker

if topic3_difficulty_starts_local_inference; then
  sudo systemctl enable \
    llmsafe-topic3-difficulty-generation-worker \
    llmsafe-topic3-difficulty-guard-worker \
    llmsafe-topic3-difficulty-router
else
  sudo systemctl disable --now \
    llmsafe-topic3-difficulty-generation-worker \
    llmsafe-topic3-difficulty-guard-worker \
    llmsafe-topic3-difficulty-router 2>/dev/null || true
fi

log "bootstrap complete"
warn "open public UFW ports manually if not already open: $(public_ports | tr '\n' ' ')"
if topic3_difficulty_starts_local_inference; then
  warn "keep Topic 3 difficulty agent/router/workers (${TOPIC3_DIFFICULTY_PORT:-6331}, ${TOPIC3_DIFFICULTY_ROUTER_PORT:-6332}, ${TOPIC3_DIFFICULTY_GENERATION_WORKER_PORT:-6333}, ${TOPIC3_DIFFICULTY_GUARD_WORKER_PORT:-6334}) local unless explicitly needed"
else
  warn "Topic 3 difficulty local inference disabled; keep 176:${TOPIC3_DIFFICULTY_ROUTER_PORT:-6332} provided by an external tunnel before starting live runs"
fi
if topic3_risk_reuses_difficulty_qwen; then
  warn "topic3-risk Agent ${TOPIC3_RISK_AGENT_PORT:-6351} reuses difficulty Qwen at ${TOPIC3_RISK_QWEN_API_BASE}; do not point TOPIC3_RISK_AGENT_URL at ${TOPIC3_DIFFICULTY_PORT:-6331}"
fi
