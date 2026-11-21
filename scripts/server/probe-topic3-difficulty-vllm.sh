#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

load_config "${SERVER_DIR}/deploy.env"

PROBE_ENV="${TOPIC3_DIFFICULTY_PROBE_CONDA_ENV:-llmsafe-topic3-difficulty-probe-py310}"
PROBE_PYTHON="${TOPIC3_DIFFICULTY_PROBE_PYTHON:-3.10}"
PROBE_TORCH_VERSION="${TOPIC3_DIFFICULTY_PROBE_TORCH_VERSION:-2.3.0}"
PROBE_TORCH_INDEX_URL="${TOPIC3_DIFFICULTY_PROBE_TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu121}"
PROBE_VLLM_VERSION="${TOPIC3_DIFFICULTY_PROBE_VLLM_VERSION:-0.4.2}"
PROBE_NUMPY_VERSION="${TOPIC3_DIFFICULTY_PROBE_NUMPY_VERSION:-1.26.4}"
PROBE_TRANSFORMERS_VERSION="${TOPIC3_DIFFICULTY_PROBE_TRANSFORMERS_VERSION:-4.40.2}"
PROBE_TOKENIZERS_VERSION="${TOPIC3_DIFFICULTY_PROBE_TOKENIZERS_VERSION:-0.19.1}"
PROBE_LM_FORMAT_ENFORCER_VERSION="${TOPIC3_DIFFICULTY_PROBE_LM_FORMAT_ENFORCER_VERSION:-0.9.8}"
PROBE_GENERATION_PORT="${TOPIC3_DIFFICULTY_PROBE_GENERATION_PORT:-16333}"
PROBE_GUARD_PORT="${TOPIC3_DIFFICULTY_PROBE_GUARD_PORT:-16334}"
PROBE_HOST="${TOPIC3_DIFFICULTY_PROBE_HOST:-127.0.0.1}"
PROBE_VLLM_SERVER_MODE="${TOPIC3_DIFFICULTY_PROBE_VLLM_SERVER_MODE:-auto}"

export HF_HOME="${TOPIC3_DIFFICULTY_HF_HOME}"

run_probe() {
  local conda_bin
  conda_bin="$(resolve_conda)"
  "${conda_bin}" run --no-capture-output -n "${PROBE_ENV}" "$@"
}

print_settings() {
  log "probe env: ${PROBE_ENV} python=${PROBE_PYTHON}"
  log "probe torch: ${PROBE_TORCH_VERSION} from ${PROBE_TORCH_INDEX_URL}"
  log "probe vLLM: ${PROBE_VLLM_VERSION}"
  log "probe compatibility pins: numpy=${PROBE_NUMPY_VERSION} transformers=${PROBE_TRANSFORMERS_VERSION} tokenizers=${PROBE_TOKENIZERS_VERSION} lm-format-enforcer=${PROBE_LM_FORMAT_ENFORCER_VERSION}"
  log "probe vLLM server mode: ${PROBE_VLLM_SERVER_MODE}"
  log "probe ports: generation=${PROBE_GENERATION_PORT} guard=${PROBE_GUARD_PORT}"
  log "hf cache: ${TOPIC3_DIFFICULTY_HF_HOME}"
}

install_probe_env() {
  print_settings
  ensure_conda_env "${PROBE_ENV}" "${PROBE_PYTHON}"
  mkdir -p "${TOPIC3_DIFFICULTY_HF_HOME}"

  log "installing probe pip tooling"
  run_probe python -m pip install --upgrade pip setuptools wheel

  log "installing probe torch CUDA wheel"
  run_probe python -m pip install \
    "torch==${PROBE_TORCH_VERSION}" \
    "torchvision==0.18.0" \
    "torchaudio==2.3.0" \
    --index-url "${PROBE_TORCH_INDEX_URL}"

  log "installing probe vLLM"
  run_probe python -m pip install "vllm==${PROBE_VLLM_VERSION}"

  log "pinning probe vLLM transitive dependencies"
  run_probe python -m pip install --force-reinstall --no-deps \
    "numpy==${PROBE_NUMPY_VERSION}" \
    "transformers==${PROBE_TRANSFORMERS_VERSION}" \
    "tokenizers==${PROBE_TOKENIZERS_VERSION}" \
    "lm-format-enforcer==${PROBE_LM_FORMAT_ENFORCER_VERSION}"

  log "probe install complete"
}

diagnose_probe_env() {
  print_settings
  log "host GPU"
  nvidia-smi || true

  log "python package diagnostics"
  run_probe python - <<'PY'
import importlib.metadata as metadata
import os

import torch

print("python ok")
print("torch", torch.__version__)
print("torch cuda", torch.version.cuda)
print("cuda available", torch.cuda.is_available())
print("cuda device count", torch.cuda.device_count())
if torch.cuda.is_available():
    print("cuda device 0", torch.cuda.get_device_name(0))
for package in ("vllm", "torch", "numpy", "transformers", "tokenizers", "lm-format-enforcer", "outlines"):
    try:
        print(package, metadata.version(package))
    except metadata.PackageNotFoundError:
        print(package, "not installed")
print("HF_HOME", os.environ.get("HF_HOME"))
PY

  log "vLLM server entrypoint diagnostics"
  if run_probe python -m vllm.entrypoints.openai.api_server --help >/dev/null 2>&1; then
    printf 'ok     %-32s %s\n' "vllm api_server module" "python -m vllm.entrypoints.openai.api_server"
  else
    printf 'failed %-32s %s\n' "vllm api_server module" "python -m vllm.entrypoints.openai.api_server"
  fi
  if run_probe python - <<'PY' >/dev/null 2>&1
import shutil
raise SystemExit(0 if shutil.which("vllm") else 1)
PY
  then
    printf 'ok     %-32s %s\n' "vllm console script" "vllm"
  else
    printf 'missing %-32s %s\n' "vllm console script" "vllm"
  fi
}

choose_vllm_server_mode() {
  case "${PROBE_VLLM_SERVER_MODE}" in
    auto)
      if run_probe python - <<'PY' >/dev/null 2>&1
import shutil
raise SystemExit(0 if shutil.which("vllm") else 1)
PY
      then
        printf '%s\n' "cli"
      else
        printf '%s\n' "module"
      fi
      ;;
    cli|module)
      printf '%s\n' "${PROBE_VLLM_SERVER_MODE}"
      ;;
    *)
      die "unknown TOPIC3_DIFFICULTY_PROBE_VLLM_SERVER_MODE=${PROBE_VLLM_SERVER_MODE}; expected auto, cli, or module"
      ;;
  esac
}

serve_model() {
  local role="$1"
  local model_source="$2"
  local served_name="$3"
  local port="$4"
  local gpu="$5"

  print_settings
  log "starting ${role} worker probe on ${PROBE_HOST}:${port}"
  log "model source: ${model_source}"
  log "served model name: ${served_name}"
  log "gpu: ${gpu}"
  warn "this is a foreground probe; stop it with Ctrl-C after /v1/models becomes ready"

  export CUDA_VISIBLE_DEVICES="${gpu}"
  export HF_HOME="${TOPIC3_DIFFICULTY_HF_HOME}"
  unset ALL_PROXY all_proxy

  local server_mode
  server_mode="$(choose_vllm_server_mode)"
  log "using vLLM ${server_mode} server entrypoint"

  if [[ "${server_mode}" == "cli" ]]; then
    run_probe vllm serve "${model_source}" \
      --host "${PROBE_HOST}" \
      --port "${port}" \
      --served-model-name "${served_name}"
  else
    run_probe python -m vllm.entrypoints.openai.api_server \
      --model "${model_source}" \
      --host "${PROBE_HOST}" \
      --port "${port}" \
      --served-model-name "${served_name}"
  fi
}

check_probe_ports() {
  local status_failed=0
  http_check "topic3-difficulty-probe-generation" "http://${PROBE_HOST}:${PROBE_GENERATION_PORT}/v1/models" || status_failed=1
  http_check "topic3-difficulty-probe-guard" "http://${PROBE_HOST}:${PROBE_GUARD_PORT}/v1/models" || status_failed=1
  return "${status_failed}"
}

usage() {
  cat <<USAGE
Usage: $0 <command>

Commands:
  install             Create/update isolated probe env and install torch/vLLM.
  diagnose            Print host GPU and probe Python package diagnostics.
  serve-generation    Start Qwen generation worker probe in the foreground.
  serve-guard         Start Qwen guard worker probe in the foreground.
  check               Check probe /v1/models endpoints.

Environment overrides:
  TOPIC3_DIFFICULTY_PROBE_CONDA_ENV=${PROBE_ENV}
  TOPIC3_DIFFICULTY_PROBE_PYTHON=${PROBE_PYTHON}
  TOPIC3_DIFFICULTY_PROBE_TORCH_VERSION=${PROBE_TORCH_VERSION}
  TOPIC3_DIFFICULTY_PROBE_TORCH_INDEX_URL=${PROBE_TORCH_INDEX_URL}
  TOPIC3_DIFFICULTY_PROBE_VLLM_VERSION=${PROBE_VLLM_VERSION}
  TOPIC3_DIFFICULTY_PROBE_NUMPY_VERSION=${PROBE_NUMPY_VERSION}
  TOPIC3_DIFFICULTY_PROBE_TRANSFORMERS_VERSION=${PROBE_TRANSFORMERS_VERSION}
  TOPIC3_DIFFICULTY_PROBE_TOKENIZERS_VERSION=${PROBE_TOKENIZERS_VERSION}
  TOPIC3_DIFFICULTY_PROBE_LM_FORMAT_ENFORCER_VERSION=${PROBE_LM_FORMAT_ENFORCER_VERSION}
  TOPIC3_DIFFICULTY_PROBE_VLLM_SERVER_MODE=${PROBE_VLLM_SERVER_MODE}
  TOPIC3_DIFFICULTY_PROBE_GENERATION_PORT=${PROBE_GENERATION_PORT}
  TOPIC3_DIFFICULTY_PROBE_GUARD_PORT=${PROBE_GUARD_PORT}

This script does not install systemd units and does not touch the production
${TOPIC3_DIFFICULTY_CONDA_ENV} environment.
USAGE
}

command="${1:-}"
case "${command}" in
  install)
    install_probe_env
    ;;
  diagnose)
    diagnose_probe_env
    ;;
  serve-generation)
    serve_model \
      "generation" \
      "${TOPIC3_DIFFICULTY_GENERATION_MODEL_SOURCE:-Qwen/Qwen3.5-9B}" \
      "${TOPIC3_DIFFICULTY_GENERATION_MODEL_NAME:-Qwen3.5-9B}" \
      "${PROBE_GENERATION_PORT}" \
      "${TOPIC3_DIFFICULTY_GENERATION_GPU:-0}"
    ;;
  serve-guard)
    serve_model \
      "guard" \
      "${TOPIC3_DIFFICULTY_GUARD_MODEL_SOURCE:-Qwen/Qwen3Guard-Gen-4B}" \
      "${TOPIC3_DIFFICULTY_GUARD_MODEL_NAME:-Qwen3Guard-Gen-4B}" \
      "${PROBE_GUARD_PORT}" \
      "${TOPIC3_DIFFICULTY_GUARD_GPU:-1}"
    ;;
  check)
    check_probe_ports
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    usage >&2
    die "unknown command: ${command}"
    ;;
esac
