"""Phase 2 — guardrails-hook output format per tool and decision.

Claude Code output follows https://code.claude.com/docs/en/hooks ; Kiro output
follows https://kiro.dev/docs/hooks/types and /actions. No network, no model.
"""

import pytest

from guardrails_hook import render_claude, render_kiro


def _decision(dec, *, obligations=None, missing=None, check_id="X-1", source="Art. X"):
    return {
        "decision": dec,
        "check_ids": [check_id],
        "reasons": [{"check_id": check_id, "decision": dec, "source": source,
                     "title": "a rule", "obligations": obligations or []}],
        "obligations": obligations or [],
        "missing_artefacts": missing or [],
    }


# --- Claude Code: UserPromptSubmit -------------------------------------------

def test_claude_prompt_block():
    out, code = render_claude.render_prompt(_decision("BLOCK"))
    assert code == 0
    assert out["decision"] == "block"
    assert "X-1" in out["reason"]


def test_claude_prompt_ask_blocks_with_human_note():
    out, code = render_claude.render_prompt(_decision("ASK"))
    assert out["decision"] == "block"
    assert "human" in out["reason"].lower()


def test_claude_prompt_warn_uses_additional_context():
    out, code = render_claude.render_prompt(
        _decision("WARN", obligations=["dpia"], missing=["dpia"]))
    assert code == 0
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "UserPromptSubmit"
    assert "dpia" in hso["additionalContext"]
    assert "decision" not in out  # WARN does not block


def test_claude_prompt_allow_is_silent():
    out, code = render_claude.render_prompt(_decision("ALLOW"))
    assert out is None
    assert code == 0


# --- Claude Code: PreToolUse --------------------------------------------------

@pytest.mark.parametrize("dec,perm", [("BLOCK", "deny"), ("ASK", "ask"), ("WARN", "allow")])
def test_claude_tool_permission_decision(dec, perm):
    out, code = render_claude.render_tool(_decision(dec))
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == perm
    assert hso["permissionDecisionReason"]


def test_claude_tool_allow_is_silent():
    out, code = render_claude.render_tool(_decision("ALLOW"))
    assert out is None


# --- Kiro: Pre Tool Use (permissionDecision on exit 0) -----------------------

@pytest.mark.parametrize("dec,perm", [("BLOCK", "deny"), ("ASK", "ask"), ("WARN", "allow")])
def test_kiro_tool_permission_decision(dec, perm):
    import json
    stdout, stderr, code = render_kiro.render(_decision(dec), "tool")
    assert code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    hso = payload["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == perm
    assert hso["permissionDecisionReason"]


def test_kiro_tool_allow_is_silent():
    stdout, stderr, code = render_kiro.render(_decision("ALLOW"), "tool")
    assert (stdout, stderr, code) == ("", "", 0)


# --- Kiro: Prompt Submit (exit code only) ------------------------------------

@pytest.mark.parametrize("dec", ["BLOCK", "ASK"])
def test_kiro_prompt_block_and_ask_exit_nonzero(dec):
    stdout, stderr, code = render_kiro.render(_decision(dec), "prompt")
    assert code == 2
    assert stdout == ""
    assert stderr  # reason on stderr


def test_kiro_prompt_warn_exits_zero_with_obligations():
    stdout, stderr, code = render_kiro.render(
        _decision("WARN", obligations=["dpia"], missing=["dpia"]), "prompt")
    assert code == 0
    assert "dpia" in stdout


def test_kiro_prompt_allow_is_silent():
    stdout, stderr, code = render_kiro.render(_decision("ALLOW"), "prompt")
    assert (stdout, stderr, code) == ("", "", 0)
