# Phase 2 — first adapters: Claude Code and Kiro

> Northwind Advisory for Halvaro Payments GmbH (fictional). This explains, in plain language, the Phase 2 build: a small hook that connects an AI coding tool to the `POST /v1/check` endpoint from Phase 1, so a developer sees a compliance decision at the moment they act. Synthetic data only; not legal advice, not a conformity claim.

## What Phase 2 adds

Phase 1 built the decision endpoint. Phase 2 puts it in front of the developer:

- **`guardrails-hook`** — a tiny, dependency-free command (Python standard library only) that each tool runs on two events: when a prompt is submitted, and before a write or shell tool call. It reads the tool's hook payload, maps it to a `/v1/check` request, calls the service, and prints the answer back in that tool's own hook format.
- **Tool hook configs** — ready-to-copy settings for **Claude Code** (`adapters/claude-code/`) and **Kiro** (`adapters/kiro/hooks/`).
- **Generated guides** — a plain-language rules file per tool (`CLAUDE.md`, Kiro steering), generated from `catalog.yaml` so they never drift from the policy.

The guides are feed-forward guidance (what to avoid, what to declare). The **hook** is the enforcement point; the guides only explain it.

## Install

`guardrails-hook` is a console script in this package:

```bash
pip install -e .        # provides the `guardrails-hook` command
```

It needs the policy service reachable. By default it calls `http://127.0.0.1:8080`; override with `GUARDRAILS_URL`. Timeout is `GUARDRAILS_TIMEOUT` seconds (default 5).

### Claude Code

Copy `adapters/claude-code/settings.example.json` to the project's `.claude/settings.json` (or the user file `~/.claude/settings.json`). It registers two hooks ([Claude Code hooks](https://code.claude.com/docs/en/hooks)):

- `UserPromptSubmit` → `guardrails-hook claude prompt`
- `PreToolUse` (matcher `Write|Edit|MultiEdit|Bash|mcp__.*`) → `guardrails-hook claude tool`

For an organisation that must guarantee the hook cannot be removed by editing a repo, deploy `adapters/claude-code/managed-settings.example.json` to the OS managed-settings path. It sets `allowManagedHooksOnly: true`, so Claude Code runs only the managed hooks and ignores project/user hooks.

### Kiro

Copy the two files under `adapters/kiro/hooks/` into the project's `.kiro/hooks/` (or `~/.kiro/hooks/` to apply to every workspace). They follow the Kiro `v1` hook schema ([Kiro hooks](https://kiro.dev/docs/hooks/), [triggers](https://kiro.dev/docs/hooks/types/), [actions](https://kiro.dev/docs/hooks/actions/)):

- `UserPromptSubmit` → `guardrails-hook kiro prompt`
- `PreToolUse` (matcher `write|shell|@mcp`) → `guardrails-hook kiro tool`

Copy the generated steering file `adapters/kiro/steering/eu-ai-compliance.md` into `.kiro/steering/` so the agent reads the rules up front.

## What the developer sees

The hook maps the four `/v1/check` decisions to each tool's native mechanism.

### Claude Code

| Decision | Prompt (`UserPromptSubmit`) | Tool call (`PreToolUse`) |
|---|---|---|
| **BLOCK** | `{"decision":"block","reason":…}` — the prompt is refused, the rule named | `permissionDecision: "deny"` with the reason |
| **ASK** | `block` with a reason that a human decision / `use-case.yaml` is needed | `permissionDecision: "ask"` |
| **WARN** | allowed; obligations + missing artefacts attached as `additionalContext` | `permissionDecision: "allow"` with the reason |
| **ALLOW** | no output (exit 0) | no output (normal permission flow) |

### Kiro

| Decision | Prompt (`UserPromptSubmit`) | Tool call (`PreToolUse`) |
|---|---|---|
| **BLOCK** | exit 2, reason on stderr → submission blocked (IDE) | exit 2, reason on stderr → tool call blocked |
| **ASK** | exit 2, reason on stderr | exit 2, reason on stderr |
| **WARN** | exit 0, obligations on stdout (added to context) | exit 0, obligations on stdout |
| **ALLOW** | no output (exit 0) | no output (exit 0) |

A Kiro shell-command hook has no JSON decision mechanism: per the [Kiro hook actions docs](https://kiro.dev/docs/hooks/actions/) a command's exit code is the only signal — exit 0 adds its stdout to the agent context, and any non-zero exit sends stderr to the agent and blocks the action (the tool call for Pre Tool Use, the submission for Prompt Submit). So the hook must exit non-zero to actually stop a write or shell call.

The mapping from a hook payload to a `/v1/check` event: a **Write/Edit** (or Kiro `fsWrite`/`strReplace`) is sent as a `diff` event carrying the new file content and path, so the secret scan and artefact stage see it; **Bash**/shell is sent as a `tool` event with the command; a prompt is a `prompt` event.

## Fail-safe

The hook never crashes the host tool and never silently allows:

- **Service down, timeout, non-200, or unparseable body → ASK.** A problem routes the action to a human, not past the gate.
- **A secret write is blocked even offline.** Before calling the service, the hook runs a local, dependency-free secret scan (a strict subset of the service's scanner). A write or command containing a key/token/password returns **BLOCK** regardless of whether the service is reachable, so the service being down can never let a secret through.

## Run the demo

```bash
make check-adapters-demo     # or: scripts/demo_adapters.sh
```

It starts the service offline (hashed-fallback embedder, no model download), pipes four payloads through the hook for **both** tools, and prints each tool's output:

- **(a) CV screening** → WARN + obligations (both tools)
- **(b) Social scoring** → blocked (Claude `decision:block`; Kiro exit 2)
- **(c) Write a file with a fake `AKIA…` credential** → denied (Claude `permissionDecision:"deny"`; Kiro exit 2 — both via the offline local scan)
- **(d) Fraud score on objective facts** → allowed (no output)

## Notes and current limits

- **Kiro field shapes** follow the public docs: the prompt text arrives in the `USER_PROMPT` environment variable for the Prompt Submit hook, and the Pre Tool Use hook receives `tool_name` / `tool_input` as JSON on stdin. The tool-input key names (`path`, `text`, `content`, `command`, …) vary by built-in tool, so the mapper reads them across a few spellings; if a tool uses a different key the field is treated as empty rather than crashing. The matcher uses Kiro's built-in category selectors (`write`, `shell`, `@mcp`).
- **Kiro blocks only via exit code.** A Kiro shell-command hook ([actions docs](https://kiro.dev/docs/hooks/actions/)) has no `permissionDecision` JSON — a non-zero exit is what blocks a Pre Tool Use call. So BLOCK and ASK exit 2 (reason on stderr) for both the prompt and tool triggers; WARN exits 0 with its obligations on stdout.
- **Kiro ASK and BLOCK are both enforced as a block.** A command hook has only an exit code, no separate "ask" channel, so ASK and BLOCK both exit 2 with the reason on stderr; the wording (`NEEDS HUMAN REVIEW` vs `BLOCKED`) distinguishes them. (Claude Code does expose a true `ask` via `permissionDecision`.)
- **Kiro prompt blocking is IDE-only.** Per the docs, a CLI/Web Prompt Submit hook cannot block the submission; there the non-zero exit still surfaces the reason to the agent as context. Pre Tool Use blocking works on all surfaces.
- **Claude `tool_input` keys** (`file_path`/`content`/`new_string`, `command`) follow the documented Write/Edit/Bash shapes; other tools (including `mcp__*`) are classified on their text argument with no file content.
- The hook is self-contained: it vendors a compact secret scanner and a tiny YAML reader so it has no dependency on the `aca` package or PyYAML when installed on a developer machine. The policy service re-validates fully.

## Scope note

Phase 2 is the editor-time adapter layer. The CI gate (Phase 3) and deploy gate (Phase 4) that enforce the same decisions on pull requests and at deploy are later phases. All of them use the single `/v1/check` contract from Phase 1.
