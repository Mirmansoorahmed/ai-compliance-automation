#!/usr/bin/env bash
# Phase 6 demo: a second hooked tool (Cursor), the MCP compliance_check tool, and
# the Agent Trust Gateway link (gateway unchanged/external). Fully offline.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m guardrails_mcp.demo
