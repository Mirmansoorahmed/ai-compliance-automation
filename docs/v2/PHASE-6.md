# Phase 6 — remaining adapters + runtime link

> Northwind Advisory for Halvaro Payments GmbH (fictional). Phase 6 extends the guardrails to Cursor, GitHub Copilot and Codex, adds an MCP tool any agent can call, and wires the integration contract with the (unchanged) Agent Trust Gateway. Synthetic data only; not legal advice, not a conformity claim.

## What Phase 6 adds

- **Cursor adapter** (`adapters/cursor/`) — Cursor supports agent hooks, so it reuses the **same `guardrails-hook` core**. `hooks.json` wires `beforeSubmitPrompt`, `beforeShellExecution` and `beforeFileEdit` to `guardrails-hook cursor ...`; the generated `rules/eu-ai-compliance.mdc` keeps the rules in context. Blocking is by exit code (non-zero blocks), the cross-tool default.
- **Copilot + Codex adapters** (`adapters/copilot/`, `adapters/codex/`) — these tools have **no deterministic blocking pre-tool hook**, so the adapter is a generated instructions file (`copilot-instructions.md`, `AGENTS.md`). Each README states plainly that this is **guidance, not enforcement**, and that the real gates are CI (`guardrails-ci`) and the MCP `compliance_check` tool.
- **MCP server** (`guardrails-mcp`) — a dependency-free JSON-RPC-over-stdio MCP server exposing one tool, **`compliance_check`**, that runs the same `/v1/check` decision engine in-process. Any MCP client (Codex, a Copilot extension, Claude Code, Cursor) can call it to get a BLOCK/ASK/WARN/ALLOW decision with rules and obligations before acting. Example client config: `adapters/mcp/mcp.example.json`.
- **Runtime link** (`aca.runtime.gateway_link`) — a thin model of the contract the **unchanged, external** Agent Trust Gateway uses: label a tool call with the Semantic Guard, let OPA (`compliance.tier`) decide, emit a redacted trace record. It does not modify the gateway.

All adapters share the one policy contract; adding a tool is configuration + a small mapper, not new policy.

## Run the demo

```bash
make check-adapters6-demo        # or: scripts/demo_adapters6.sh
```

Offline output:

```
1. Cursor adapter (same guardrails-hook core)
   social prompt   -> exit 2 ([guardrails: BLOCKED] ...)
   CV prompt       -> exit 0 (no output)         # ALLOW without a declared use-case
   secret write    -> exit 2 ([guardrails: BLOCKED] ...)
2. MCP compliance_check tool
   social  -> BLOCK (isError=True)
   CV      -> ALLOW (isError=False)
3. Agent Trust Gateway link (gateway unchanged/external)
   tool call 'mcp__db__run' -> tier=deny allowed=False
   trace: {"tool": "mcp__db__run", "tier": "deny", "allowed": false, "concept_ids": ["AIA-5-1-c"], ...}
```

This is the Phase 6 target: the same social-scoring / secret scenario enforced in a **second hooked tool** (Cursor), available as an **MCP tool** for tools without hooks, and **one gateway-blocked tool call in the trace**. (The CV prompt is ALLOW here because no `use-case.yaml` is attached in this snippet; with a declared high-risk use case it is WARN + obligations, as in the Phase 2 demo.)

## Limits

- **Copilot and Codex are guidance-only.** Their instructions steer the model but cannot block a tool call; enforcement for their changes is CI + the MCP tool. The adapter READMEs say this explicitly.
- **Cursor field names vary by version.** `hooks.json` targets current event names and the mapper reads fields defensively; confirm the event names for your Cursor version (see `adapters/cursor/README.md`).
- **The MCP server implements just enough of MCP** (`initialize`, `tools/list`, `tools/call`) for the `compliance_check` tool — it is not a full MCP framework.
- **The Agent Trust Gateway is external and unchanged.** `aca.runtime` models the integration contract so it can be tested offline; it is not the gateway itself. A real end-to-end run against the deployed gateway is to be run by the owner.

## To be run by the owner

- A live end-to-end run against the deployed Agent Trust Gateway (external repo), confirming the same deny appears in the gateway's own trace.
- Registering `guardrails-mcp` in each agent's MCP config and confirming the tool is discovered and called.

## Scope note

Phase 6 completes tool coverage and the runtime link. Phase 7 collects the decision records from the editor hook, CI, deploy and this runtime link into one evidence trace.
