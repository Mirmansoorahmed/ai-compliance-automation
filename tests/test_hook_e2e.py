"""Phase 2 — end to end: pipe the hook fixtures through guardrails-hook.

Starts the real /v1/check service (hashed-fallback embedder, no model download)
on a background thread, points the hook at it via GUARDRAILS_URL, then feeds the
committed stdin fixtures through ``cli.run`` for both tools and checks the
rendered decision and exit code. This is the whole path a developer's tool
exercises: hook JSON -> normalised event -> /v1/check -> tool-format output.
"""

import io
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from aca.check.service import CheckService
from aca.config import load_config
from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.api.app import LabelService, make_handler
from aca.guard.embeddings import HashedEmbedder
from aca.guard.service import SemanticGuard
from aca.usecase.registry import load_registry

from guardrails_hook import cli

_FIX = Path(__file__).resolve().parent / "fixtures" / "hooks"
_CV_YAML = _FIX / "use-case-cv.yaml"


@pytest.fixture(scope="module")
def service_url():
    guard = SemanticGuard(adapters=[LocalEmbeddingsAdapter(embedder=HashedEmbedder(dim=256))])
    check = CheckService(guard=guard, use_cases=load_registry())
    label = LabelService(load_config("oss"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(label, check))
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()


def _run(tool, event, fixture, monkeypatch, url, *, user_prompt=None, use_case=None):
    monkeypatch.setenv("GUARDRAILS_URL", url)
    if user_prompt is not None:
        monkeypatch.setenv("USER_PROMPT", user_prompt)
    if use_case is not None:
        monkeypatch.setenv("GUARDRAILS_USE_CASE", str(use_case))
    else:
        monkeypatch.delenv("GUARDRAILS_USE_CASE", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO((_FIX / fixture).read_text()))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli.run([tool, event])
    return out.getvalue(), err.getvalue(), code


# --- Claude Code --------------------------------------------------------------

def test_claude_social_prompt_blocks(service_url, monkeypatch):
    out, err, code = _run("claude", "prompt", "claude/prompt-social.json",
                          monkeypatch, service_url)
    payload = json.loads(out)
    assert payload["decision"] == "block"
    assert "AIA-5-1-c" in payload["reason"]


def test_claude_cv_prompt_warns_with_obligations(service_url, monkeypatch):
    out, err, code = _run("claude", "prompt", "claude/prompt-cv.json",
                          monkeypatch, service_url, use_case=_CV_YAML)
    payload = json.loads(out)
    hso = payload["hookSpecificOutput"]
    assert hso["hookEventName"] == "UserPromptSubmit"
    assert "worker_information" in hso["additionalContext"]


def test_claude_fraud_prompt_allows_silently(service_url, monkeypatch):
    out, err, code = _run("claude", "prompt", "claude/prompt-fraud.json",
                          monkeypatch, service_url, use_case=None)
    assert out == ""  # ALLOW -> no output
    assert code == 0


def test_claude_write_secret_denies(service_url, monkeypatch):
    out, err, code = _run("claude", "tool", "claude/tool-write-secret.json",
                          monkeypatch, service_url)
    payload = json.loads(out)
    hso = payload["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert "secret" in hso["permissionDecisionReason"].lower()


# --- Kiro ---------------------------------------------------------------------

def test_kiro_social_prompt_blocks_exit2(service_url, monkeypatch):
    social = json.loads((_FIX / "claude" / "prompt-social.json").read_text())["prompt"]
    out, err, code = _run("kiro", "prompt", "kiro/prompt-session.json",
                          monkeypatch, service_url, user_prompt=social)
    assert code == 2
    assert "AIA-5-1-c" in err


def test_kiro_cv_prompt_warns(service_url, monkeypatch):
    cv = json.loads((_FIX / "claude" / "prompt-cv.json").read_text())["prompt"]
    out, err, code = _run("kiro", "prompt", "kiro/prompt-session.json",
                          monkeypatch, service_url, user_prompt=cv, use_case=_CV_YAML)
    assert code == 0
    assert "worker_information" in out


def test_kiro_fraud_prompt_allows(service_url, monkeypatch):
    fraud = json.loads((_FIX / "claude" / "prompt-fraud.json").read_text())["prompt"]
    out, err, code = _run("kiro", "prompt", "kiro/prompt-session.json",
                          monkeypatch, service_url, user_prompt=fraud)
    assert (out, err, code) == ("", "", 0)


def test_kiro_write_secret_denies(service_url, monkeypatch):
    out, err, code = _run("kiro", "tool", "kiro/tool-write-secret.json",
                          monkeypatch, service_url)
    payload = json.loads(out)
    hso = payload["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert "secret" in hso["permissionDecisionReason"].lower()
