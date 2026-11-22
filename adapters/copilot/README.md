# GitHub Copilot adapter

GitHub Copilot does not expose a deterministic, blocking pre-tool hook the way Claude Code, Kiro and Cursor do. So this adapter is a **custom instructions file**, not an enforcement point.

## Install

Copy `copilot-instructions.md` to `.github/copilot-instructions.md` in the repo. Copilot loads it as repository custom instructions, so the model sees the EU AI compliance rules (what to refuse, what to declare) while it works.

## Limits (important)

- **Guidance only.** The instructions steer the model; they do not block a prompt or a tool call. A determined or careless path can still produce a non-compliant change.
- **Enforcement is elsewhere.** The real gates for a Copilot-authored change are the **CI check** (`guardrails-ci`) on the pull request and, where wired, the **MCP `compliance_check` tool**. A BLOCK item here is something the PR will fail on.
- The file is generated from the catalog (`adapters/generate_guides.py`); do not edit by hand.
