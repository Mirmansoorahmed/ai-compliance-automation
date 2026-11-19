"""Render a decision as Claude Code hook output (https://code.claude.com/docs/en/hooks).

Returns ``(stdout_obj_or_None, exit_code)``. The CLI prints the JSON (if any)
and exits with the code.

UserPromptSubmit:
  BLOCK -> {"decision":"block","reason":...}
  ASK   -> block with a reason that a human review / use-case.yaml is needed
  WARN  -> allow; attach obligations + missing artefacts as additionalContext
           via hookSpecificOutput (UserPromptSubmit additionalContext)
  ALLOW -> no output, exit 0

PreToolUse:
  hookSpecificOutput.permissionDecision = deny | ask | allow
  BLOCK -> deny ; ASK -> ask ; WARN -> allow (with the reason) ; ALLOW -> allow/none
"""

from __future__ import annotations

from guardrails_hook.messages import full_message, summary


def render_prompt(decision: dict):
    d = decision.get("decision", "ASK")

    if d == "BLOCK":
        return {"decision": "block", "reason": full_message(decision)}, 0

    if d == "ASK":
        reason = full_message(decision) + (
            "\nThis needs a human decision. Record an interpretation (or complete "
            "use-case.yaml) and have it reviewed before continuing."
        )
        return {"decision": "block", "reason": reason}, 0

    if d == "WARN":
        return {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": full_message(decision),
            }
        }, 0

    # ALLOW -> no output
    return None, 0


def render_tool(decision: dict):
    d = decision.get("decision", "ASK")
    mapping = {"BLOCK": "deny", "ASK": "ask", "WARN": "allow", "ALLOW": "allow"}
    perm = mapping.get(d, "ask")

    if d == "ALLOW":
        # Nothing to add; let Claude apply its normal permission flow.
        return None, 0

    reason = full_message(decision) if d != "WARN" else summary(decision)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": perm,
            "permissionDecisionReason": reason,
        }
    }, 0
