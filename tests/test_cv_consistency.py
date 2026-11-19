"""Phase 6 fix — the CV-screening story gives the SAME decision across every
adapter (Claude Code, Kiro, Cursor) and the MCP compliance_check tool.

With the CV use-case declared (Annex III 4(a)), every path must be WARN with the
same obligations — matching the Phase 2/3/4 demos. Runs the hook paths against a
live in-process service and the MCP tool in-process; offline hashed embedder.
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
from aca.guard.embeddings import build_embedder
from aca.guard.service import SemanticGuard

from guardrails_hook import cli
from guardrails_mcp.server import ComplianceServer

CV = "Build a CV screening tool that scores applicants and shortlists the top 20."

CV_USE_CASE = {
    "id": "uc-hr-cv-screening",
    "title": "CV pre-screening for apprenticeships",
    "ai_system": True,
    "role": "deployer",
    "annex_iii": ["4(a)"],
    "decision_effect": "assists",
    "artefacts": {
        "risk_management": None, "dpia": None, "fria": None,
        "oversight_plan": None, "eval_report": None, "worker_information": None,
    },
}

_CV_YAML = """id: uc-hr-cv-screening
title: CV pre-screening for apprenticeships
ai_system: true
role: deployer
annex_iii:
  - 4(a)
decision_effect: assists
artefacts:
  risk_management: null
  dpia: null
  fria: null
  oversight_plan: null
  eval_report: null
  worker_information: null
"""


@pytest.fixture(scope="module")
def service_url():
    guard = SemanticGuard(adapters=[LocalEmbeddingsAdapter(embedder=build_embedder(allow_hashed_fallback=True, dim=256), dim=256)])
    httpd = ThreadingHTTPServer(("127.0.0.1", 0),
                                make_handler(LabelService(load_config("oss")),
                                             CheckService(guard=guard)))
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()


@pytest.fixture(scope="module")
def cv_yaml(tmp_path_factory):
    p = tmp_path_factory.mktemp("uc") / "use-case.yaml"
    p.write_text(_CV_YAML, encoding="utf-8")
    return p


def _expected_obligations():
    # The authoritative obligations for the CV use case, from the engine itself.
    from aca.check.decide import CheckPolicy, decide_checks
    from aca.check.detectors import ANNEX_III_RELATED
    r = decide_checks(["AIA-A3-4a"], CheckPolicy.load(),
                      related=list(ANNEX_III_RELATED["AIA-A3-4a"]))
    return r.decision, set(r.obligations)


def _hook_obligations_from_stdout_or_err(text):
    # WARN obligations are rendered as "- <key> (missing)" lines.
    import re
    return set(re.findall(r"- (\w+) \(", text))


def _run_hook(tool, event, raw, monkeypatch, url, *, user_prompt=None, use_case=None):
    monkeypatch.setenv("GUARDRAILS_URL", url)
    if user_prompt is not None:
        monkeypatch.setenv(f"{'CURSOR_PROMPT' if tool == 'cursor' else 'USER_PROMPT'}", user_prompt)
    if use_case is not None:
        monkeypatch.setenv("GUARDRAILS_USE_CASE", str(use_case))
    else:
        monkeypatch.delenv("GUARDRAILS_USE_CASE", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(raw)))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli.run([tool, event])
    return out.getvalue(), err.getvalue(), code


def test_cv_warn_and_obligations_consistent_across_adapters(service_url, cv_yaml, monkeypatch):
    expected_decision, expected_obl = _expected_obligations()
    assert expected_decision == "WARN"
    assert expected_obl  # non-empty

    # Claude: WARN -> additionalContext JSON with the obligations.
    out, _, _ = _run_hook("claude", "prompt", {"prompt": CV}, monkeypatch, service_url,
                          use_case=cv_yaml)
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert _hook_obligations_from_stdout_or_err(ctx) == expected_obl

    # Kiro: WARN -> exit 0, obligations on stdout.
    out, _, code = _run_hook("kiro", "prompt", {}, monkeypatch, service_url,
                             user_prompt=CV, use_case=cv_yaml)
    assert code == 0
    assert _hook_obligations_from_stdout_or_err(out) == expected_obl

    # Cursor: WARN -> exit 0, obligations on stdout (same contract as Kiro).
    out, _, code = _run_hook("cursor", "prompt", {}, monkeypatch, service_url,
                             user_prompt=CV, use_case=cv_yaml)
    assert code == 0
    assert _hook_obligations_from_stdout_or_err(out) == expected_obl


def test_cv_warn_and_obligations_consistent_in_mcp(service_url):
    expected_decision, expected_obl = _expected_obligations()
    server = ComplianceServer()
    resp = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": "compliance_check",
                                     "arguments": {"event": "prompt", "text": CV,
                                                   "use_case": CV_USE_CASE}}})
    d = resp["result"]["structuredContent"]
    assert d["decision"] == expected_decision == "WARN"
    assert set(d["obligations"]) == expected_obl
    assert resp["result"]["isError"] is False


def test_cv_without_use_case_is_allow_everywhere(service_url, monkeypatch):
    # Without a declared use case, the CV prompt is correctly ALLOW (no Annex III
    # declaration to warn on) — this is consistent, not a bug.
    out, _, code = _run_hook("cursor", "prompt", {}, monkeypatch, service_url,
                             user_prompt=CV, use_case=None)
    assert code == 0 and out == ""
    server = ComplianceServer()
    resp = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                          "params": {"name": "compliance_check",
                                     "arguments": {"event": "prompt", "text": CV}}})
    assert resp["result"]["structuredContent"]["decision"] == "ALLOW"
