#!/usr/bin/env bash
# Phase 1 demo: the four POST /v1/check calls, printed as decisions.
# Runs fully offline (hashed-fallback embedder; no model download).
#
#   1. CV screening (Annex III 4(a)) -> WARN + obligations
#   2. Social scoring (Art. 5(1)(c)) -> BLOCK
#   3. Fraud score (objective facts) -> ALLOW
#   4. Secret pasted into a diff     -> BLOCK
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m aca.check.demo
