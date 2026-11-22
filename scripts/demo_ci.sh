#!/usr/bin/env bash
# Phase 3 demo: the CI gate over two fixtures, printed as decision + exit code +
# pending checklist. Runs fully offline (hashed-fallback embedder; no download).
#
#   1. Hardcoded test credential (secret.diff)  -> BLOCK, exit 1
#   2. CV screening feature (cv-feature.diff)   -> WARN,  exit 0 (missing artefacts listed)
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m guardrails_ci.demo
