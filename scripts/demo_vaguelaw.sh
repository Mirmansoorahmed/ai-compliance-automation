#!/usr/bin/env bash
# Phase 5b demo: the vague-law classifier on the CV-screening story, offline,
# using the default local (open-source) backend. The closed Jev backend is NOT
# used. Offline probabilities are a smoke signal; real accuracy/ECE/ASK-rate are
# measured by the owner with the trained model.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m aca.vaguelaw.demo
