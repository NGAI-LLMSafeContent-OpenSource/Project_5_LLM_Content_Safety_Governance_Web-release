#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

load_config "${SERVER_DIR}/deploy.env"

log "host"
hostnamectl || true
uname -a
whoami
pwd

log "toolchain"
git --version
node -v
npm -v
pnpm -v
json-server --version
rsync --version | head -1
nginx -v
systemctl --version | head -1
"$(resolve_conda)" run -n "${CONDA_ENV}" python --version
python3 --version

log "resources"
df -h /data || df -h "${DEPLOY_ROOT}"
free -h
nproc

log "target port occupancy"
occupied=0
for port in $(target_ports); do
  if sudo ss -lntp | grep -E ":${port}\b" >/dev/null; then
    sudo ss -lntp | grep -E ":${port}\b"
    occupied=1
  else
    printf 'free   %s\n' "${port}"
  fi
done

log "ufw"
sudo ufw status || true

log "github connectivity"
curl -I https://github.com --max-time 10 >/dev/null && echo "github ok" || echo "github unavailable"

log "topic1 value_qa paths"
printf 'repo   %s\n' "${TOPIC1_VALUE_QA_PROJECT_ROOT}"
printf 'python %s\n' "${TOPIC1_VALUE_QA_PYTHON}"
if [[ -d "${TOPIC1_VALUE_QA_PROJECT_ROOT}" ]]; then
  printf 'ok     topic1-value-qa repo exists\n'
else
  printf 'missing topic1-value-qa repo\n'
fi
if [[ -x "${TOPIC1_VALUE_QA_PYTHON}" ]]; then
  printf 'ok     topic1-value-qa venv python exists\n'
else
  printf 'missing topic1-value-qa venv python\n'
fi

log "topic3 risk live_run paths"
printf 'repo   %s\n' "${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}"
printf 'agent  %s\n' "${TOPIC3_RISK_AGENT_URL}"
printf 'qwen   %s\n' "${TOPIC3_RISK_QWEN_API_BASE}"
printf 'model  %s\n' "${TOPIC3_RISK_QWEN_MODEL}"
printf 'reuse  %s\n' "${TOPIC3_RISK_REUSE_DIFFICULTY_QWEN}"
printf 'conda  %s\n' "${TOPIC3_RISK_CONDA_ENV}"
printf 'compliance %s timeout=%s\n' "${COMPLIANCE_EDIT_BASE_URL}" "${COMPLIANCE_EDIT_TIMEOUT_SECONDS}"
if [[ -d "${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}" ]]; then
  printf 'ok     topic3-risk repo exists\n'
else
  printf 'missing topic3-risk repo\n'
fi
if [[ -f "${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}/qwen_agent_server/live_run_adapter.py" ]]; then
  printf 'ok     topic3-risk live_run_adapter.py exists\n'
else
  printf 'missing topic3-risk live_run_adapter.py\n'
fi
if [[ -f "${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}/qwen_agent_server/agent_server.py" ]]; then
  printf 'ok     topic3-risk agent_server.py exists\n'
else
  printf 'missing topic3-risk agent_server.py\n'
fi
if [[ -f "${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}/qwen_agent_server/qa_risk_dataset.py" ]]; then
  printf 'ok     topic3-risk qa_risk_dataset.py exists\n'
else
  printf 'missing topic3-risk qa_risk_dataset.py\n'
fi

log "topic3 cultural assessment paths"
printf 'repo   %s\n' "${TOPIC3_CULTURAL_ASSESSMENT_DIR}"
printf 'root   %s\n' "${CULTURAL_ASSESSMENT_ROOT}"
printf 'console %s\n' "${CULTURAL_ASSESSMENT_CONSOLE_BASE_URL}"
if [[ -d "${CULTURAL_ASSESSMENT_ROOT}/culture_eval_benchmark" ]]; then
  printf 'ok     topic3-cultural-assessment benchmark exists\n'
else
  printf 'missing topic3-cultural-assessment culture_eval_benchmark\n'
fi
if [[ -f "${CULTURAL_ASSESSMENT_ROOT}/.env" ]] && grep -q '^DEEPSEEK_API_KEY=' "${CULTURAL_ASSESSMENT_ROOT}/.env"; then
  printf 'ok     topic3-cultural-assessment .env contains DEEPSEEK_API_KEY\n'
else
  printf 'missing topic3-cultural-assessment .env DEEPSEEK_API_KEY for dynamic jobs\n'
fi

log "topic3 cultural corpus paths"
printf 'repo   %s\n' "${TOPIC3_CULTURAL_CORPUS_DIR}"
printf 'root   %s\n' "${CULTURAL_CORPUS_GENERATOR_ROOT}"
printf 'runs   %s\n' "${CULTURAL_CORPUS_RUNS_DIR}"
if [[ -d "${CULTURAL_CORPUS_RUNS_DIR}" ]]; then
  printf 'ok     topic3-cultural-corpus runs dir exists\n'
else
  printf 'missing topic3-cultural-corpus runs dir\n'
fi
if find "${CULTURAL_CORPUS_RUNS_DIR}" -maxdepth 2 -name samples.jsonl -print -quit 2>/dev/null | grep -q .; then
  printf 'ok     topic3-cultural-corpus samples.jsonl exists\n'
else
  printf 'missing topic3-cultural-corpus samples.jsonl\n'
fi

if [[ "${occupied}" -eq 1 ]]; then
  warn "one or more target ports are occupied"
else
  log "target ports are free"
fi
