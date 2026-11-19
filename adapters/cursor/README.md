# Cursor adapter

Cursor supports agent hooks, so it uses the same `guardrails-hook` core as Claude Code and Kiro.

## Install

1. Put `guardrails-hook` on PATH (`pip install -e .` in this repo) and make the policy service reachable (`GUARDRAILS_URL`, default `http://127.0.0.1:8080`).
2. Copy `hooks.json` to `.cursor/hooks.json` in the project (or `~/.cursor/hooks.json` for every project).
3. Copy the generated rules file `rules/eu-ai-compliance.mdc` to `.cursor/rules/eu-ai-compliance.mdc` so the rules stay in the model's context.

## Behaviour

`guardrails-hook cursor <prompt|tool>` reads Cursor's hook JSON from stdin, maps it to a `/v1/check` event, and signals through the **exit code** (the cross-tool default, same contract as Kiro):

| Decision | Exit | Effect |
|---|---|---|
| BLOCK | 2 | reason on stderr → action blocked |
| ASK | 2 | reason on stderr → blocked, a human decides |
| WARN | 0 | obligations on stdout (shown to the agent) |
| ALLOW | 0 | no output |

A secret in a file edit or shell command is blocked locally even if the service is down (same offline secret pre-check as the other adapters).

## Limits and version note

- Cursor's hook event names and payload field names have changed across versions. `hooks.json` targets `beforeSubmitPrompt`, `beforeShellExecution` and `beforeFileEdit`; the mapper reads prompt/command/file fields defensively across spellings. **Confirm the exact event names for your Cursor version** and adjust `hooks.json` if they differ — if an unknown field is used, the mapper treats it as empty rather than crashing.
- The prompt text may be delivered on stdin or via a `CURSOR_PROMPT` environment variable depending on version; the mapper checks both.
