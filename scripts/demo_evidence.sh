#!/usr/bin/env bash
# Phase 7 demo: the evidence pack v2 auditor view — one use case from prompt to
# production, with every decision, the obligations + approvals, and the ISO
# 42001 / EU AI Act mapping. Fully offline. No code, paths or hashes in the body.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m aca.evidence_pack.demo
