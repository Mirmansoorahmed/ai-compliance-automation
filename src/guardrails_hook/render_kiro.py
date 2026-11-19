"""Render a decision as Kiro hook output (https://kiro.dev/docs/hooks/ , /types , /actions).

Two Kiro mechanisms are used, per the trigger:

Pre Tool Use (``event == "tool"``) — a Run Command hook can return a JSON
decision on stdout (exit 0): ``hookSpecificOutput.permissionDecision`` =
``deny`` | ``ask`` | ``allow`` with a ``permissionDecisionReason``. This gives a
precise ASK (ask a human) distinct from BLOCK (deny):

  BLOCK -> exit 0, {permissionDecision:"deny",  reason}   (denied)
  ASK   -> exit 0, {permissionDecision:"ask",   reason}   (human decides)
  WARN  -> exit 0, {permissionDecision:"allow",  reason}  (continues; obligations shown)
  ALLOW -> exit 0, no output                               (normal permission flow)

Prompt Submit (``event == "prompt"``) — no permissionDecision mechanism; a
command hook signals through its exit code only (a non-zero exit blocks the
submission in the IDE and sends stderr to the agent; on CLI/Web a Prompt Submit
hook cannot block, so the reason is still surfaced as context):

  BLOCK -> exit 2, reason on stderr
  ASK   -> exit 2, reason on stderr   (no separate "ask" for prompt hooks)
  WARN  -> exit 0, obligations on stdout
  ALLOW -> exit 0, no output

Returns ``(stdout_text, stderr_text, exit_code)``.
"""

from __future__ import annotations

import json

from guardrails_hook.messages import full_message, summary

_PERM = {"BLOCK": "deny", "ASK": "ask", "WARN": "allow", "ALLOW": "allow"}


def _tool(decision: dict):
    d = decision.get("decision", "ASK")
    if d == "ALLOW":
        return "", "", 0
    reason = full_message(decision) if d != "WARN" else summary(decision)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": _PERM.get(d, "ask"),
            "permissionDecisionReason": reason,
        }
    }
    return json.dumps(out), "", 0


def _prompt(decision: dict):
    d = decision.get("decision", "ASK")
    if d in ("BLOCK", "ASK"):
        prefix = "BLOCKED" if d == "BLOCK" else "NEEDS HUMAN REVIEW"
        return "", f"[guardrails: {prefix}] {full_message(decision)}", 2
    if d == "WARN":
        return f"[guardrails: WARN] {full_message(decision)}", "", 0
    return "", "", 0


def render(decision: dict, event: str = "tool"):
    if event == "prompt":
        return _prompt(decision)
    return _tool(decision)
