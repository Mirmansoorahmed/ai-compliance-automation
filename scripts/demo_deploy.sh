#!/usr/bin/env bash
# Phase 4 demo: the deploy gate denies, then allows. Fully offline (no opa
# binary, no cluster needed — uses the Python mirror of policy/deploy.rego).
#
#   1. First deploy              -> DENY (DPIA, oversight plan, ... missing)
#   2. After artefacts + 2 approvals -> ALLOW
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m aca.check.deploy_demo
