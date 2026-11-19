#!/usr/bin/env bash
# Phase 5 demo: per-concept exemplar smoke check, fully offline (hashed
# embedder). This is a DATA sanity signal, NOT a model result — the real recall
# numbers are measured by the owner on a machine with the MiniLM model.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m aca.eval.concepts
