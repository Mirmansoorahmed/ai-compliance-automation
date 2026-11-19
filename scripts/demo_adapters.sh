#!/usr/bin/env bash
# Phase 2 demo: four payloads piped through guardrails-hook for BOTH tools
# (Claude Code + Kiro), printed as each tool's own hook output. Runs fully
# offline (hashed-fallback embedder; no model download) and starts/stops the
# /v1/check service itself.
#
#   (a) CV screening                   -> WARN + obligations
#   (b) Social scoring                 -> blocked
#   (c) Write a file containing a secret -> denied (offline local scan)
#   (d) Fraud score (objective facts)  -> allowed
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m guardrails_hook.demo
