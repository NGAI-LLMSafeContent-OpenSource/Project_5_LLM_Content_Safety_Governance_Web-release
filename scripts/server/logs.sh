#!/usr/bin/env bash
set -euo pipefail

target="${1:-all}"

if [[ "${target}" == "all" ]]; then
  sudo journalctl -f \
    -u llmsafe-topic3-benchmark \
    -u llmsafe-topic3-diversity-data \
    -u llmsafe-topic3-diversity-backend \
    -u llmsafe-topic3-diversity-frontend \
    -u llmsafe-topic3-cultural-assessment-console \
    -u llmsafe-topic3-cultural-assessment-console-v2 \
    -u llmsafe-topic3-difficulty-generation-worker \
    -u llmsafe-topic3-difficulty-guard-worker \
    -u llmsafe-topic3-difficulty-router \
    -u llmsafe-topic3-difficulty-agent \
    -u llmsafe-topic3-risk-agent \
    -u llmsafe-topic2-dynbench \
    -u llmsafe-topic2-filterguard \
    -u llmsafe-topic1-backend \
    -u llmsafe-topic1-frontend \
    -u llmsafe-project5-backend \
    -u llmsafe-project5-governance-worker \
    -u llmsafe-project5-topic2-showcase
else
  if [[ "${target}" != *.service ]]; then
    target="${target}.service"
  fi
  sudo journalctl -f -u "${target}"
fi
