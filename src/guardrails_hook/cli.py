"""guardrails-hook CLI: `guardrails-hook <tool> <event>` (also python -m guardrails_hook).

<tool>  in {claude, kiro}
<event> in {prompt, tool}

Reads the tool's hook JSON from stdin, maps it to the /v1/check event, applies a
local offline secret pre-check, calls the policy service (fail-safe ASK), and
prints the decision in the tool's own format. Exit codes follow each tool's
hook contract (see render_claude / render_kiro).
"""

from __future__ import annotations

import json
import sys

from guardrails_hook import client, mapping, render_claude, render_kiro
from guardrails_hook.secrets import has_secret
from guardrails_hook.usecase import resolve_use_case

_SECRET_BLOCK = {
    "decision": "BLOCK",
    "check_ids": ["SEC-SECRETS"],
    "reasons": [{"check_id": "SEC-SECRETS", "decision": "BLOCK",
                 "source": "CWE-798; gitleaks",
                 "title": "a secret (key/token/password) must not be written into code",
                 "obligations": []}],
    "obligations": [],
    "missing_artefacts": [],
    "_local_secret": True,
}


def _read_stdin_json() -> dict:
    data = sys.stdin.read() or "{}"
    try:
        obj = json.loads(data)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


def _decide(tool: str, event: str, raw: dict, *, opener=None) -> dict:
    mapped = mapping.map_event(tool, event, raw)

    # Local, offline secret pre-check: a secret in a write/command is BLOCKED
    # even if the service is down or would allow it. Strict subset of the
    # service scanner, so it never over-allows.
    scan_text = " ".join(str(mapped.get(k, "")) for k in ("diff", "text"))
    if mapped.get("event") in ("diff", "tool") and has_secret(scan_text):
        return _SECRET_BLOCK

    use_case = resolve_use_case(mapped.get("repo"))
    payload = {
        "event": mapped["event"],
        "text": mapped.get("text", ""),
        "diff": mapped.get("diff", ""),
        "tool": mapped.get("tool", tool),
        "tool_call": mapped.get("tool_call", ""),
        "path": mapped.get("path", ""),
        "repo": mapped.get("repo", ""),
        "user": mapped.get("user", ""),
    }
    if use_case is not None:
        payload["use_case"] = use_case

    kwargs = {"opener": opener} if opener is not None else {}
    return client.post_check(payload, **kwargs)


def run(argv: list[str], *, opener=None) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: guardrails-hook <claude|kiro> <prompt|tool>\n")
        return 2
    tool, event = argv[0], argv[1]
    if tool not in ("claude", "kiro"):
        sys.stderr.write(f"unknown tool {tool!r}; expected claude|kiro\n")
        return 2
    if event not in ("prompt", "tool"):
        sys.stderr.write(f"unknown event {event!r}; expected prompt|tool\n")
        return 2

    raw = _read_stdin_json()
    decision = _decide(tool, event, raw, opener=opener)

    if tool == "claude":
        if event == "prompt":
            out, code = render_claude.render_prompt(decision)
        else:
            out, code = render_claude.render_tool(decision)
        if out is not None:
            sys.stdout.write(json.dumps(out))
        return code

    # kiro
    stdout_text, stderr_text, code = render_kiro.render(decision, event)
    if stdout_text:
        sys.stdout.write(stdout_text)
    if stderr_text:
        sys.stderr.write(stderr_text)
    return code


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
