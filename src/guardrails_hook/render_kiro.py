"""Render a decision as Kiro hook output (https://kiro.dev/docs/hooks/ , /types , /actions).

Kiro shell-command hooks signal the host through the process exit code only
(https://kiro.dev/docs/hooks/actions/): exit 0 adds the command's stdout to the
agent context, and any non-zero exit sends stderr to the agent AND blocks the
action — the tool invocation for a Pre Tool Use hook, the submission for a
Prompt Submit hook. There is no JSON ``permissionDecision`` mechanism for a
command action, so the hook must exit non-zero to actually stop a tool call.

Both triggers therefore use the same exit-code contract:

  BLOCK -> exit 2, reason on stderr   (blocked)
  ASK   -> exit 2, reason on stderr   (blocked; a human must decide — a Kiro
           command hook has no separate "ask", so ASK is enforced as a block)
  WARN  -> exit 0, obligations on stdout (continues; added to context)
  ALLOW -> exit 0, no output

Note (Prompt Submit surfaces): per the docs a CLI/Web Prompt Submit hook cannot
block the submission; there the non-zero exit still surfaces the reason to the
agent as context. Pre Tool Use blocking works on all surfaces.

Returns ``(stdout_text, stderr_text, exit_code)``.
"""

from __future__ import annotations

from guardrails_hook.messages import full_message


def render(decision: dict, event: str = "tool"):
    d = decision.get("decision", "ASK")

    if d in ("BLOCK", "ASK"):
        prefix = "BLOCKED" if d == "BLOCK" else "NEEDS HUMAN REVIEW"
        return "", f"[guardrails: {prefix}] {full_message(decision)}", 2

    if d == "WARN":
        return f"[guardrails: WARN] {full_message(decision)}", "", 0

    # ALLOW
    return "", "", 0
