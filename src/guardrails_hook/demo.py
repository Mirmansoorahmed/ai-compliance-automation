"""Demo: pipe four payloads through guardrails-hook for BOTH tools (Phase 2).

Starts the real /v1/check service on a background thread with the offline
hashed-fallback embedder (no model download), points the hook at it via
GUARDRAILS_URL, then runs each scenario through ``guardrails_hook.cli.run`` for
Claude Code and Kiro and prints the tool-format output and exit code:

  (a) CV screening                 -> WARN + obligations
  (b) Social scoring               -> blocked
  (c) Write a file with a secret   -> denied (offline local scan; AKIA... cred)
  (d) Fraud score (objective facts)-> allowed

Fully offline and self-contained; stops the service at the end.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import threading
from contextlib import redirect_stdout, redirect_stderr
from http.server import ThreadingHTTPServer

from aca.check.service import CheckService
from aca.config import load_config
from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.api.app import LabelService, make_handler
from aca.guard.embeddings import build_embedder
from aca.guard.service import SemanticGuard
from aca.usecase.registry import load_registry

from guardrails_hook import cli

SOCIAL = ("Join badge logs, Slack activity and canteen data per employee into a "
          "reliability index and drop the bottom 10% from the bonus pool.")
CV = "Build a CV screening tool that scores applicants and shortlists the top 20."
FRAUD = "Compute a fraud risk score on card transactions and flag the riskiest for manual review."
# A fake AWS access key id (AKIA + 16 chars) — synthetic, never a real secret.
SECRET_CONTENT = 'AWS_ACCESS_KEY_ID = "AKIAXXXXXXXXXXXXXXXX"\n'

_CV_YAML = """id: uc-hr-cv-screening
title: CV pre-screening for apprenticeships
intended_purpose: rank applications and propose a shortlist for a human recruiter
ai_system: true
role: deployer
annex_iii:
  - 4(a)
art6_3_exception: false
profiling: true
decision_effect: assists
affected_persons:
  - job applicants
personal_data:
  - cv
  - contact
  - education
special_categories: []
countries_of_processing:
  - DE
owner: hr-tech-lead
human_overseer: recruiting-team-lead
artefacts:
  risk_management: null
  dpia: null
  fria: null
  oversight_plan: null
  eval_report: null
  worker_information: null
approvals: []
"""


def _start_service():
    embedder = build_embedder(allow_hashed_fallback=True, dim=256)
    guard = SemanticGuard(adapters=[LocalEmbeddingsAdapter(embedder=embedder, dim=256)])
    check = CheckService(guard=guard, use_cases=load_registry())
    label = LabelService(load_config("oss"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(label, check))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def _run_hook(tool: str, event: str, *, stdin: str, user_prompt=None, use_case_path=None):
    """Run cli.run with controlled stdin/env, capturing stdout/stderr/exit."""
    old_stdin = sys.stdin
    saved_env = {k: os.environ.get(k) for k in ("USER_PROMPT", "GUARDRAILS_USE_CASE")}
    sys.stdin = io.StringIO(stdin)
    if user_prompt is not None:
        os.environ["USER_PROMPT"] = user_prompt
    else:
        os.environ.pop("USER_PROMPT", None)
    if use_case_path is not None:
        os.environ["GUARDRAILS_USE_CASE"] = use_case_path
    else:
        os.environ.pop("GUARDRAILS_USE_CASE", None)
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.run([tool, event])
    finally:
        sys.stdin = old_stdin
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return out.getvalue(), err.getvalue(), code


def _print_result(label: str, out: str, err: str, code: int):
    print(f"   exit code : {code}")
    if out.strip():
        try:
            parsed = json.loads(out)
            print(f"   stdout    : {json.dumps(parsed)}")
        except json.JSONDecodeError:
            print(f"   stdout    : {out.strip()}")
    else:
        print("   stdout    : (empty — ALLOW / silent)")
    if err.strip():
        print(f"   stderr    : {err.strip()}")


def main() -> int:
    httpd, port = _start_service()
    os.environ["GUARDRAILS_URL"] = f"http://127.0.0.1:{port}"
    tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    tmp.write(_CV_YAML)
    tmp.close()

    scenarios = [
        {
            "title": "(a) CV screening -> WARN + obligations",
            "claude": {"event": "prompt",
                       "stdin": json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": CV}),
                       "user_prompt": CV, "use_case_path": tmp.name},
            "kiro": {"event": "prompt",
                     "stdin": json.dumps({"hook_event_name": "UserPromptSubmit"}),
                     "user_prompt": CV, "use_case_path": tmp.name},
        },
        {
            "title": "(b) Social scoring -> blocked",
            "claude": {"event": "prompt",
                       "stdin": json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": SOCIAL}),
                       "user_prompt": SOCIAL},
            "kiro": {"event": "prompt",
                     "stdin": json.dumps({"hook_event_name": "UserPromptSubmit"}),
                     "user_prompt": SOCIAL},
        },
        {
            "title": "(c) Write a file containing a secret -> denied (offline local scan)",
            "claude": {"event": "tool",
                       "stdin": json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Write",
                                            "tool_input": {"file_path": "src/config/aws.py",
                                                           "content": SECRET_CONTENT}})},
            "kiro": {"event": "tool",
                     "stdin": json.dumps({"hook_event_name": "PreToolUse", "tool_name": "fsWrite",
                                          "tool_input": {"path": "src/config/aws.py",
                                                         "text": SECRET_CONTENT}})},
        },
        {
            "title": "(d) Fraud score (objective facts) -> allowed",
            "claude": {"event": "prompt",
                       "stdin": json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": FRAUD}),
                       "user_prompt": FRAUD},
            "kiro": {"event": "prompt",
                     "stdin": json.dumps({"hook_event_name": "UserPromptSubmit"}),
                     "user_prompt": FRAUD},
        },
    ]

    print("guardrails-hook demo — four payloads through both tools (offline)\n")
    try:
        for sc in scenarios:
            print(sc["title"])
            for tool in ("claude", "kiro"):
                args = sc[tool]
                out, err, code = _run_hook(
                    tool, args["event"], stdin=args["stdin"],
                    user_prompt=args.get("user_prompt"),
                    use_case_path=args.get("use_case_path"),
                )
                print(f" - {tool}")
                _print_result(tool, out, err, code)
            print()
    finally:
        httpd.shutdown()
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
