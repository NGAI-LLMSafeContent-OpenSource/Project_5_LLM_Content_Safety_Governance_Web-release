#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

load_config "${SERVER_DIR}/deploy.env"

status_failed=0

log "systemd services"
services=(
  llmsafe-topic3-benchmark
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
fi
if topic3_difficulty_starts_local_inference; then
  services=(
    llmsafe-topic3-difficulty-generation-worker
    llmsafe-topic3-difficulty-guard-worker
    llmsafe-topic3-difficulty-router
    "${services[@]}"
  )
fi
if topic3_risk_snapshot_ready; then
  services=(
    llmsafe-topic3-risk-agent
    "${services[@]}"
  )
fi
for service in "${services[@]}"; do
  service_status_line "${service}" || status_failed=1
done

log "http health"
http_check "project5-backend" "http://127.0.0.1:${PROJECT5_BACKEND_PORT:-5800}/health" || status_failed=1
http_check "project5-frontend-nginx" "http://127.0.0.1:${PROJECT5_FRONTEND_PORT:-5173}" || status_failed=1
http_check "project5-api-same-origin" "http://127.0.0.1:${PROJECT5_FRONTEND_PORT:-5173}/api/health" || status_failed=1
http_check "topic3-benchmark" "http://127.0.0.1:${TOPIC3_BENCHMARK_PORT:-6006}/api/taxonomies" || status_failed=1
http_check "topic3-diversity-data" "http://127.0.0.1:${TOPIC3_DIVERSITY_DATA_PORT:-6323}/samples" || status_failed=1
http_check "topic3-diversity-backend" "http://127.0.0.1:${TOPIC3_DIVERSITY_API_PORT:-6322}/api/health" || status_failed=1
http_check "topic3-diversity-frontend" "http://127.0.0.1:${TOPIC3_DIVERSITY_UI_PORT:-6321}" || status_failed=1
http_check "topic3-cultural-assessment-console" "http://127.0.0.1:${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_PORT:-8877}/api/health" || status_failed=1
http_check "topic3-cultural-assessment-console-v2" "http://127.0.0.1:${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_V2_PORT:-8878}/api/health" || status_failed=1
http_check "project5-cultural-corpus-samples" "http://127.0.0.1:${PROJECT5_BACKEND_PORT:-5800}/api/output/culture/corpus-samples?include_live_runs=true&limit=1" || status_failed=1
http_check "project5-cultural-assessment-static" "http://127.0.0.1:${PROJECT5_BACKEND_PORT:-5800}/api/output/culture-assessment/datasets" || status_failed=1
http_check "project5-cultural-assessment-console" "http://127.0.0.1:${PROJECT5_BACKEND_PORT:-5800}/api/output/culture-assessment/console/health" || status_failed=1
http_check "topic3-compliance-edit" "${COMPLIANCE_EDIT_BASE_URL%/}/healthz" || status_failed=1
if topic3_difficulty_starts_local_inference; then
  http_check "topic3-difficulty-generation-worker" "http://127.0.0.1:${TOPIC3_DIFFICULTY_GENERATION_WORKER_PORT:-6333}/v1/models" || status_failed=1
  http_check "topic3-difficulty-guard-worker" "http://127.0.0.1:${TOPIC3_DIFFICULTY_GUARD_WORKER_PORT:-6334}/v1/models" || status_failed=1
  http_check "topic3-difficulty-router" "http://127.0.0.1:${TOPIC3_DIFFICULTY_ROUTER_PORT:-6332}/healthz" || status_failed=1
else
  http_check "topic3-difficulty-external-router" "http://127.0.0.1:${TOPIC3_DIFFICULTY_ROUTER_PORT:-6332}/healthz" || status_failed=1
  http_check "topic3-difficulty-router-models" "http://127.0.0.1:${TOPIC3_DIFFICULTY_ROUTER_PORT:-6332}/v1/models" || status_failed=1
fi
http_check "topic3-difficulty-agent" "http://127.0.0.1:${TOPIC3_DIFFICULTY_PORT:-6331}/api/health" || status_failed=1
http_check "topic1-backend" "http://127.0.0.1:${TOPIC1_BACKEND_PORT:-6102}/health" || status_failed=1
http_check "topic2-showcase" "http://127.0.0.1:${TOPIC2_SHOWCASE_PORT:-6201}/health" || status_failed=1
http_check "topic2-dynbench" "http://127.0.0.1:${TOPIC2_DYNBENCH_PORT:-8766}/api/health" || status_failed=1
http_check "topic2-filterguard" "http://127.0.0.1:${TOPIC2_FILTERGUARD_PORT:-6211}/health" || status_failed=1

log "topic3 risk live_run"
if topic3_risk_snapshot_ready; then
  http_check "topic3-risk-agent" "http://127.0.0.1:${TOPIC3_RISK_AGENT_PORT:-6351}/health" || status_failed=1
else
  http_check_optional "topic3-risk-agent" "http://127.0.0.1:${TOPIC3_RISK_AGENT_PORT:-6351}/health" || \
    warn "topic3-risk snapshot missing; live_run unavailable until Project_3_Dynamic_Risk_Benchmark_Generation is synced"
fi
http_check "topic3-risk-qwen" "${TOPIC3_RISK_QWEN_API_BASE%/}/models" || status_failed=1
if [[ -f "${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}/qwen_agent_server/live_run_adapter.py" ]]; then
  printf 'ok     %-32s %s\n' "topic3-risk-cli" "${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}"
else
  printf 'pending %-32s %s\n' "topic3-risk-cli" "${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}"
fi

log "topic1 value_qa CLI"
if [[ -x "${TOPIC1_VALUE_QA_PYTHON}" ]] && \
  (cd "${TOPIC1_VALUE_QA_PROJECT_ROOT}" && "${TOPIC1_VALUE_QA_PYTHON}" -m benchmark.cli list-skills | grep -q "value_qa"); then
  printf 'ok     %-32s %s\n' "topic1-value-qa-cli" "${TOPIC1_VALUE_QA_PROJECT_ROOT}"
else
  printf 'failed %-32s %s\n' "topic1-value-qa-cli" "${TOPIC1_VALUE_QA_PROJECT_ROOT}"
  status_failed=1
fi

log "external URLs"
cat <<URLS
Project 5 frontend (nginx):  http://${PUBLIC_HOST}:${PROJECT5_FRONTEND_PORT:-5173}
Project 5 API (same-origin): http://${PUBLIC_HOST}:${PROJECT5_FRONTEND_PORT:-5173}/api
Project 5 backend local:     http://127.0.0.1:${PROJECT5_BACKEND_PORT:-5800}
Topic 1 frontend:            http://${PUBLIC_HOST}:${TOPIC1_FRONTEND_PORT:-6101}
Topic 1 backend:             http://${PUBLIC_HOST}:${TOPIC1_BACKEND_PORT:-6102}
Topic 2 showcase:            http://${PUBLIC_HOST}:${TOPIC2_SHOWCASE_PORT:-6201}
Topic 2 DynBench:            http://${PUBLIC_HOST}:${TOPIC2_DYNBENCH_PORT:-8766}/agent
Topic 2 FilterGuard:         http://${PUBLIC_HOST}:${TOPIC2_FILTERGUARD_PORT:-6211}
Topic 3 Benchmark:           http://${PUBLIC_HOST}:${TOPIC3_BENCHMARK_PORT:-6006}
Topic 3 diversity UI:        http://${PUBLIC_HOST}:${TOPIC3_DIVERSITY_UI_PORT:-6321}
Topic 3 diversity API:       http://${PUBLIC_HOST}:${TOPIC3_DIVERSITY_API_PORT:-6322}
Topic 3 diversity data:      http://${PUBLIC_HOST}:${TOPIC3_DIVERSITY_DATA_PORT:-6323}/samples
Topic 3 cultural assessment: http://127.0.0.1:${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_PORT:-8877} (Project 5 BFF only)
Topic 3 cultural assess v2:  http://127.0.0.1:${TOPIC3_CULTURAL_ASSESSMENT_CONSOLE_V2_PORT:-8878} (Project 5 BFF only)
URLS

exit "${status_failed}"
