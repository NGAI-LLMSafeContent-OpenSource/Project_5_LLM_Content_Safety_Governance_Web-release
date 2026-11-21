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
  plan      Print the planned manual GPU runtime layout.
  status    Print expected pid/log/model locations.
  install   Placeholder for Phase 2 vLLM env installation.
  start     Placeholder for Phase 2 manual GPU worker startup.
  stop      Placeholder for Phase 2 manual GPU worker shutdown.
  smoke     Placeholder for Phase 2 runtime HTTP checks.

GPU workers remain opt-in. Phase 1 does not install vLLM, load models, or start
any CUDA process.
USAGE
}

model_map() {
  printf '{"%s":"http://127.0.0.1:%s/v1","%s":"http://127.0.0.1:%s/v1"}\n' \
    "${TOPIC3_DIFFICULTY_GENERATION_MODEL_NAME:-Qwen3.5-9B}" \
    "${TOPIC3_DIFFICULTY_GENERATION_WORKER_PORT:-6333}" \
    "${TOPIC3_DIFFICULTY_GUARD_MODEL_NAME:-Qwen3Guard-Gen-4B}" \
    "${TOPIC3_DIFFICULTY_GUARD_WORKER_PORT:-6334}"
}

print_runtime_plan() {
  cat <<PLAN
AutoDL dynamic difficulty runtime planned for Phase 2:
  agent       127.0.0.1:${TOPIC3_DIFFICULTY_PORT:-6331}
  router      127.0.0.1:${TOPIC3_DIFFICULTY_ROUTER_PORT:-6332}
  generation  127.0.0.1:${TOPIC3_DIFFICULTY_GENERATION_WORKER_PORT:-6333} gpu=${TOPIC3_DIFFICULTY_GENERATION_GPU:-0}
  guard       127.0.0.1:${TOPIC3_DIFFICULTY_GUARD_WORKER_PORT:-6334} gpu=${TOPIC3_DIFFICULTY_GUARD_GPU:-1}
  model_map   $(model_map)
PLAN
}

print_runtime_status_paths() {
  cat <<STATUS
conda_env=${TOPIC3_DIFFICULTY_CONDA_ENV:-llmsafe-topic3-difficulty-py310}
vllm_spec=${TOPIC3_DIFFICULTY_VLLM_SPEC:-vllm==0.25.1}
hf_home=${HF_HOME}
generation_model_dir=${TOPIC3_DIFFICULTY_GENERATION_MODEL_DIR:-${MODEL_ROOT}/Qwen3.5-9B}
guard_model_dir=${TOPIC3_DIFFICULTY_GUARD_MODEL_DIR:-${MODEL_ROOT}/Qwen3Guard-Gen-4B}
agent_pid=$(pid_file topic3-difficulty-agent)
router_pid=$(pid_file topic3-difficulty-router)
generation_pid=$(pid_file topic3-difficulty-generation)
guard_pid=$(pid_file topic3-difficulty-guard)
agent_log=$(log_file topic3-difficulty-agent)
router_log=$(log_file topic3-difficulty-router)
generation_log=$(log_file topic3-difficulty-generation)
guard_log=$(log_file topic3-difficulty-guard)
STATUS
}

command="${1:-}"
case "${command}" in
  plan)
    print_runtime_plan
    ;;
  status)
    print_runtime_status_paths
    ;;
  install|start|stop|smoke)
    print_runtime_plan
    warn "${command} is a Phase 2 placeholder; GPU runtime was not changed"
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    usage >&2
    die "unknown command: ${command}"
    ;;
esac
