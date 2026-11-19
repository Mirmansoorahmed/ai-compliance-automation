"""Demo: Phase 6 — a second tool (Cursor), the MCP tool, and the gateway link.

Offline (hashed embedder). Three parts:

  1. Cursor adapter: the CV / social-scoring / secret scenario through
     guardrails-hook as a SECOND hooked tool (same core as Claude/Kiro).
  2. MCP compliance_check tool: an agent calls it and gets a decision.
  3. Agent Trust Gateway link (gateway unchanged/external): a social-scoring
     tool call is DENIED and a trace record is emitted.
"""

from __future__ import annotations

import io
import json
import os
import threading
from http.server import ThreadingHTTPServer

from aca.check.service import CheckService
from aca.config import load_config
from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.api.app import LabelService, make_handler
from aca.guard.embeddings import build_embedder
from aca.guard.service import SemanticGuard
from aca.policy.decide import PolicyData, load_policy_data
from aca.runtime import GatewayLink

from guardrails_hook import cli
from guardrails_mcp.server import ComplianceServer


def _start_service():
    embedder = build_embedder(allow_hashed_fallback=True, dim=256)
    guard = SemanticGuard(adapters=[LocalEmbeddingsAdapter(embedder=embedder, dim=256)])
    check = CheckService(guard=guard)
    label = LabelService(load_config("oss"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(label, check))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]

SOCIAL = ("Join badge logs, Slack activity and canteen data per employee into a "
          "reliability index and drop the bottom 10% from the bonus pool.")
CV = "Build a CV screening tool that scores applicants and shortlists the top 20."
SECRET = 'AWS_ACCESS_KEY_ID = "AKIAXXXXXXXXXXXXXXXX"'


def _run_cursor(event, raw, *, user_prompt=None):
    import os
    import sys
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps(raw))
    if user_prompt is not None:
        os.environ["CURSOR_PROMPT"] = user_prompt
    else:
        os.environ.pop("CURSOR_PROMPT", None)
    out, err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        code = cli.run(["cursor", event])
    finally:
        sys.stdin, sys.stdout, sys.stderr = old_stdin, old_out, old_err
        os.environ.pop("CURSOR_PROMPT", None)
    return out.getvalue(), err.getvalue(), code


def main() -> int:
    print("Phase 6 demo — second tool (Cursor), MCP tool, gateway link (offline)\n")

    httpd, port = _start_service()
    os.environ["GUARDRAILS_URL"] = f"http://127.0.0.1:{port}"
    try:
        print("1. Cursor adapter (same guardrails-hook core)")
        _, err, code = _run_cursor("prompt", {}, user_prompt=SOCIAL)
        print(f"   social prompt   -> exit {code} ({err.strip()[:60]}...)")
        out, _, code = _run_cursor("prompt", {}, user_prompt=CV)
        print(f"   CV prompt       -> exit {code} ({'WARN + obligations on stdout' if out.strip() else 'no output'})")
        _, err, code = _run_cursor("tool", {"file_path": "aws.py", "content": SECRET})
        print(f"   secret write    -> exit {code} ({err.strip()[:45]}...)")
        print()
    finally:
        httpd.shutdown()

    print("2. MCP compliance_check tool")
    server = ComplianceServer()
    for name, text in (("social", SOCIAL), ("CV", CV)):
        resp = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                              "params": {"name": "compliance_check",
                                         "arguments": {"event": "prompt", "text": text}}})
        d = resp["result"]["structuredContent"]
        print(f"   {name:7} -> {d['decision']} (isError={resp['result']['isError']})")
    print()

    print("3. Agent Trust Gateway link (gateway unchanged/external)")
    base = load_policy_data()
    policy = PolicyData(thresholds=base.thresholds,
                        confirmed_prohibited_patterns=["AIA-5-1-c/joined-behaviour-adverse-action"])
    link = GatewayLink(
        LocalEmbeddingsAdapter(embedder=build_embedder(allow_hashed_fallback=True, dim=256), dim=256),
        policy=policy)
    decision = link.check_tool_call(tool="mcp__db__run", text=SOCIAL)
    trace = link.trace("mcp__db__run", decision, note="social scoring at runtime")
    print(f"   tool call 'mcp__db__run' -> tier={decision.tier} allowed={decision.allowed}")
    print(f"   trace: {json.dumps({k: v for k, v in trace.to_dict().items() if k != 'ts'})}")
    print()
    print("Note: the Agent Trust Gateway is a separate, unchanged repository; this "
          "exercises the integration contract offline.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
