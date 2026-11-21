#!/usr/bin/env bash
# Read-only deployment self-check.
#
# It never calls sudo and never mutates state, so it is safe to run on a
# production host, and it can run in an agent/CI session without a TTY. Use it
# before bootstrap.sh / deploy-all.sh to catch the failure modes that otherwise
# only surface deep inside a deploy (after systemd and nginx were modified).
#
# Exit code: 0 when no ERROR was found, 1 otherwise. WARN does not fail.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
# common.sh enables errexit; a checker must keep going after a failed probe.
set +e

usage() {
  cat <<'USAGE'
Usage: bash scripts/server/check-config.sh [options]

Read-only checks: bash syntax, deploy.env keys/values, required commands,
listening ports, repository checkouts. Never calls sudo.

Options:
  --config=PATH   Deploy env file (default: scripts/server/deploy.env)
  --dump          Print the resolved KEY=value config and exit
  --network       Also run `git ls-remote` on every configured repo (slow)
  -h, --help      Show this help
USAGE
}

CONFIG_PATH="${SERVER_DIR}/deploy.env"
DUMP_CONFIG=false
CHECK_NETWORK=false

while (($# > 0)); do
  case "$1" in
    --config)
      (($# >= 2)) || { printf 'error: --config needs a value\n' >&2; exit 2; }
      CONFIG_PATH="$2"
      shift
      ;;
    --config=*)
      CONFIG_PATH="${1#*=}"
      ;;
    --dump)
      DUMP_CONFIG=true
      ;;
    --network)
      CHECK_NETWORK=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'error: unknown argument: %s (see --help)\n' "$1" >&2
      exit 2
      ;;
  esac
  shift
done

load_config "${CONFIG_PATH}"

if bool_true "${DUMP_CONFIG}"; then
  dump_config
  exit 0
fi

failures=0
warnings=0

ok() {
  printf 'ok       %-28s %s\n' "$1" "${2:-}"
}

warn_check() {
  warnings=$((warnings + 1))
  printf 'warn     %-28s %s\n' "$1" "${2:-}"
}

fail_check() {
  failures=$((failures + 1))
  printf 'FAIL     %-28s %s\n' "$1" "${2:-}"
}

log "config: ${CONFIG_PATH}"
if [[ ! -f "${CONFIG_PATH}" ]]; then
  fail_check "deploy.env" "${CONFIG_PATH} is missing; deploy scripts would fall back to deploy.env.example"
else
  config_mode="$(stat -c '%a' "${CONFIG_PATH}" 2>/dev/null || printf '?')"
  ok "deploy.env" "mode ${config_mode}"
  case "${config_mode}" in
    6[0-4]0|600|400) ;;
    *)
      if [[ "${config_mode}" != "?" ]]; then
        warn_check "deploy.env mode" "${config_mode} is readable by group/other; prefer chmod 600"
      fi
      ;;
  esac
fi

log "shell syntax"
for script in "${SCRIPT_DIR}"/*.sh "${SCRIPT_DIR}"/lib/*.sh; do
  [[ -f "${script}" ]] || continue
  name="${script#"${SERVER_DIR}/"}"
  if syntax_output="$(bash -n "${script}" 2>&1)"; then
    ok "${name}"
  else
    fail_check "${name}" "${syntax_output}"
  fi
done

log "config sanity"
if validate_output="$(validate_config "${CONFIG_PATH}" 2>&1)"; then
  if grep -q 'problem(s) above' <<<"${validate_output}"; then
    warn_check "deploy.env values" "see the warnings printed above"
    printf '%s\n' "${validate_output}"
  else
    ok "deploy.env values"
  fi
else
  fail_check "deploy.env values" "${validate_output}"
fi

# A hand-trimmed deploy.env is the documented usage now: common.sh defaults every
# repo URL from its repo name. Show the effective result so a silent default is
# easy to spot.
log "repository URLs"
for pair in \
  "PROJECT5:${PROJECT5_REPO_URL}" \
  "TOPIC1:${TOPIC1_REPO_URL}" \
  "TOPIC1_VALUE_QA:${TOPIC1_VALUE_QA_REPO_URL}" \
  "TOPIC2_FLYWHEEL:${TOPIC2_FLYWHEEL_REPO_URL}" \
  "TOPIC2_FILTERGUARD:${TOPIC2_FILTERGUARD_REPO_URL}" \
  "TOPIC3_BENCHMARK:${TOPIC3_BENCHMARK_REPO_URL}" \
  "TOPIC3_CULTURAL_GEN:${TOPIC3_CULTURAL_GEN_REPO_URL}" \
  "TOPIC3_CULTURAL_CORPUS:${TOPIC3_CULTURAL_CORPUS_REPO_URL}" \
  "TOPIC3_CULTURAL_ASSESSMENT:${TOPIC3_CULTURAL_ASSESSMENT_REPO_URL}" \
  "TOPIC3_COMPLIANCE:${TOPIC3_COMPLIANCE_REPO_URL}" \
  "TOPIC3_DIFFICULTY:${TOPIC3_DIFFICULTY_REPO_URL}"; do
  label="${pair%%:*}"
  url="${pair#*:}"
  if [[ -z "${url}" ]]; then
    fail_check "${label}" "empty repository URL"
  elif [[ "${url}" == *"://"* ]]; then
    fail_check "${label}" "${url} uses HTTPS; the deploy scripts expect git@github.com:... so the server SSH key is used"
  else
    ok "${label}" "${url}"
  fi
done

log "required commands"
for cmd in git node npm pnpm rsync sudo systemctl nginx json-server conda; do
  cmd_path="$(type -P "${cmd}" 2>/dev/null || command -v "${cmd}" 2>/dev/null || true)"
  if [[ -n "${cmd_path}" ]]; then
    ok "${cmd}" "${cmd_path}"
  else
    warn_check "${cmd}" "not found in PATH"
  fi
done
if ! command -v uv >/dev/null 2>&1 && [[ ! -x "${HOME}/.local/bin/uv" ]]; then
  warn_check "uv" "not found; Topic 3 compliance editing will be skipped"
fi

log "listening ports"
if command -v ss >/dev/null 2>&1; then
  listening="$(ss -ltn 2>/dev/null | awk 'NR > 1 {print $4}')"
elif command -v lsof >/dev/null 2>&1; then
  listening="$(lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | awk 'NR > 1 {print $9}')"
else
  listening=""
  warn_check "port probe" "neither ss nor lsof is available"
fi
if [[ -n "${listening}" ]]; then
  while IFS= read -r port; do
    [[ -n "${port}" ]] || continue
    if grep -qE "[:.]${port}$" <<<"${listening}"; then
      warn_check "port ${port}" "already listening (an existing service, a leftover, or this deploy already running)"
    else
      ok "port ${port}" "free"
    fi
  done < <(target_ports)
fi

log "repository checkouts"
for pair in \
  "project5:${PROJECT5_DIR}" \
  "topic1:${TOPIC1_DIR}" \
  "topic1-value-qa:${TOPIC1_VALUE_QA_DIR}" \
  "topic2-dynbench:${TOPIC2_FLYWHEEL_DIR}" \
  "topic2-filterguard:${TOPIC2_FILTERGUARD_DIR}" \
  "topic3-benchmark:${TOPIC3_BENCHMARK_DIR}" \
  "topic3-cultural-gen:${TOPIC3_CULTURAL_GEN_DIR}" \
  "topic3-cultural-corpus:${TOPIC3_CULTURAL_CORPUS_DIR}" \
  "topic3-cultural-assessment:${TOPIC3_CULTURAL_ASSESSMENT_DIR}" \
  "topic3-compliance:${TOPIC3_COMPLIANCE_DIR}" \
  "topic3-difficulty:${TOPIC3_DIFFICULTY_DIR}" \
  "topic3-risk:${TOPIC3_RISK_DIR}"; do
  label="${pair%%:*}"
  path="${pair#*:}"
  if [[ -d "${path}/.git" ]]; then
    ok "${label}" "git checkout at ${path}"
  elif [[ -d "${path}" ]]; then
    ok "${label}" "directory at ${path} (not a git checkout)"
  else
    warn_check "${label}" "missing at ${path}; deploy-all.sh will clone it"
  fi
done

if [[ "${TOPIC3_RISK_REPO_NAME}" == "${TOPIC3_RISK_DIR##*/}" ]] && [[ ! -f "${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}/qwen_agent_server/agent_server.py" ]]; then
  warn_check "topic3-risk snapshot" "missing ${TOPIC3_RISK_BENCHMARK_PROJECT_ROOT}/qwen_agent_server/agent_server.py; risk live_run stays unavailable (deploy tolerates this)"
fi

if bool_true "${CHECK_NETWORK}"; then
  log "repository reachability (git ls-remote)"
  for pair in \
    "PROJECT5:${PROJECT5_REPO_URL}" \
    "TOPIC1:${TOPIC1_REPO_URL}" \
    "TOPIC1_VALUE_QA:${TOPIC1_VALUE_QA_REPO_URL}" \
    "TOPIC2_FLYWHEEL:${TOPIC2_FLYWHEEL_REPO_URL}" \
    "TOPIC2_FILTERGUARD:${TOPIC2_FILTERGUARD_REPO_URL}" \
    "TOPIC3_BENCHMARK:${TOPIC3_BENCHMARK_REPO_URL}" \
    "TOPIC3_CULTURAL_GEN:${TOPIC3_CULTURAL_GEN_REPO_URL}" \
    "TOPIC3_CULTURAL_CORPUS:${TOPIC3_CULTURAL_CORPUS_REPO_URL}" \
    "TOPIC3_CULTURAL_ASSESSMENT:${TOPIC3_CULTURAL_ASSESSMENT_REPO_URL}" \
    "TOPIC3_COMPLIANCE:${TOPIC3_COMPLIANCE_REPO_URL}" \
    "TOPIC3_DIFFICULTY:${TOPIC3_DIFFICULTY_REPO_URL}"; do
    label="${pair%%:*}"
    url="${pair#*:}"
    [[ -n "${url}" ]] || continue
    if timeout 20 git ls-remote --heads "${url}" >/dev/null 2>&1; then
      ok "${label}" "reachable over SSH"
    else
      fail_check "${label}" "cannot reach ${url} (check the SSH key and ssh.github.com:443 fallback)"
    fi
  done
fi

log "summary: ${failures} failure(s), ${warnings} warning(s)"
if ((failures > 0)); then
  exit 1
fi
exit 0
