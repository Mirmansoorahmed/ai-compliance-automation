# Codex adapter

OpenAI Codex / agent runners read an `AGENTS.md` at the repo root for working instructions. This adapter is that file — **guidance, not enforcement**.

## Install

Copy `AGENTS.md` to the repo root (or the directory Codex reads). It carries the EU AI compliance rules generated from the catalog.

## Limits (important)

- **Guidance only.** `AGENTS.md` instructs the agent; it is not a blocking pre-tool hook. It cannot by itself stop a non-compliant tool call.
- **Enforcement is elsewhere.** The real gates for a Codex-authored change are the **CI check** (`guardrails-ci`) and, where wired, the **MCP `compliance_check` tool** that the agent can call to get a decision before acting.
- Generated from the catalog (`adapters/generate_guides.py`); do not edit by hand.
