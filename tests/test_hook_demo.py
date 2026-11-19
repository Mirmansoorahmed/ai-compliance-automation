"""Phase 2 — the adapters demo produces the four expected outcomes per tool.

Runs the demo's own machinery (offline service + hook) and asserts each
scenario's decision for both Claude Code and Kiro. No network, no model.
"""

import io
import json
import os
import sys
from contextlib import redirect_stdout, redirect_stderr

import pytest

from guardrails_hook import demo


@pytest.fixture(scope="module")
def running_service():
    httpd, port = demo._start_service()
    os.environ["GUARDRAILS_URL"] = f"http://127.0.0.1:{port}"
    try:
        yield
    finally:
        httpd.shutdown()


def _claude_decision(out, code):
    if out.strip() == "":
        return "ALLOW"
    payload = json.loads(out)
    if payload.get("decision") == "block":
        return "BLOCK/ASK"
    hso = payload.get("hookSpecificOutput", {})
    perm = hso.get("permissionDecision")
    if perm == "deny":
        return "DENY"
    if "additionalContext" in hso:
        return "WARN"
    return "OTHER"


def test_demo_social_blocks_both_tools(running_service):
    out, err, code = demo._run_hook(
        "claude", "prompt",
        stdin=json.dumps({"prompt": demo.SOCIAL}), user_prompt=demo.SOCIAL)
    assert _claude_decision(out, code) == "BLOCK/ASK"
    out, err, code = demo._run_hook(
        "kiro", "prompt", stdin="{}", user_prompt=demo.SOCIAL)
    assert code == 2 and "AIA-5-1-c" in err


def test_demo_secret_write_denied_both_tools(running_service):
    content = demo.SECRET_CONTENT
    out, err, code = demo._run_hook(
        "claude", "tool",
        stdin=json.dumps({"tool_name": "Write",
                          "tool_input": {"file_path": "aws.py", "content": content}}))
    assert _claude_decision(out, code) == "DENY"
    out, err, code = demo._run_hook(
        "kiro", "tool",
        stdin=json.dumps({"tool_name": "fsWrite",
                          "tool_input": {"path": "aws.py", "text": content}}))
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_demo_fraud_allows_both_tools(running_service):
    out, err, code = demo._run_hook(
        "claude", "prompt",
        stdin=json.dumps({"prompt": demo.FRAUD}), user_prompt=demo.FRAUD)
    assert (out, code) == ("", 0)
    out, err, code = demo._run_hook(
        "kiro", "prompt", stdin="{}", user_prompt=demo.FRAUD)
    assert (out, err, code) == ("", "", 0)


def test_demo_main_runs_and_stops(running_service, monkeypatch):
    # Smoke: the full demo main() runs end to end without raising.
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(io.StringIO()):
        rc = demo.main()
    assert rc == 0
    text = buf.getvalue()
    assert "(a) CV screening" in text
    assert "(d) Fraud score" in text
