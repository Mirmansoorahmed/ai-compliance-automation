#!/usr/bin/env bash
# Phase 8 demo: the packaged policy service (the same one the container runs),
# started in-process and exercised with /healthz + three /v1/check calls. Fully
# offline. With Docker, use deploy/docker/docker-compose.yml instead.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m aca.guard.api.demo_stack
