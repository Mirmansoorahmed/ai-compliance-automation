"""Phase 2 — guardrails-hook fail-safe behaviour.

When the policy service is unreachable, times out, or returns garbage, the hook
returns ASK (never a silent ALLOW, never a crash). A secret write is still
BLOCKED locally even with the service down, because the hook runs an offline
secret pre-check that cannot be over-ridden by the service being unavailable.
No network, no model.
"""

import json
import urllib.error

import pytest

from guardrails_hook import cli, client


def _down_opener(*a, **k):
    raise urllib.error.URLError("connection refused")


def _timeout_opener(*a, **k):
    raise TimeoutError("timed out")


class _FakeResp:
    def __init__(self, body, status=200):
        self._body = body.encode("utf-8")
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_post_check_service_down_asks():
    out = client.post_check({"event": "prompt", "text": "x"}, opener=_down_opener)
    assert out["decision"] == "ASK"
    assert out["_failsafe"] is True


def test_post_check_timeout_asks():
    out = client.post_check({"event": "prompt", "text": "x"}, opener=_timeout_opener)
    assert out["decision"] == "ASK"


def test_post_check_non_200_asks():
    out = client.post_check({"event": "prompt"},
                            opener=lambda *a, **k: _FakeResp("{}", status=503))
    assert out["decision"] == "ASK"


def test_post_check_bad_json_asks():
    out = client.post_check({"event": "prompt"},
                            opener=lambda *a, **k: _FakeResp("not json"))
    assert out["decision"] == "ASK"


def test_post_check_missing_decision_asks():
    out = client.post_check({"event": "prompt"},
                            opener=lambda *a, **k: _FakeResp('{"labels": []}'))
    assert out["decision"] == "ASK"


def test_decide_prompt_asks_when_service_down():
    out = cli._decide("claude", "prompt", {"prompt": "build a thing"},
                      opener=_down_opener)
    assert out["decision"] == "ASK"


def test_secret_write_blocks_offline_even_with_service_down():
    # A Write carrying a secret must BLOCK locally, before (and regardless of)
    # the service call. The opener raising proves no over-allow via the service.
    raw = {"tool_name": "Write",
           "tool_input": {"file_path": "aws.py",
                          "content": 'KEY = "AKIAXXXXXXXXXXXXXXXX"'}}
    out = cli._decide("claude", "tool", raw, opener=_down_opener)
    assert out["decision"] == "BLOCK"
    assert "SEC-SECRETS" in out["check_ids"]
    assert out.get("_local_secret") is True


def test_kiro_secret_write_blocks_offline():
    raw = {"tool_name": "fsWrite",
           "tool_input": {"path": "aws.py",
                          "text": 'KEY = "AKIAXXXXXXXXXXXXXXXX"'}}
    out = cli._decide("kiro", "tool", raw, opener=_down_opener)
    assert out["decision"] == "BLOCK"
