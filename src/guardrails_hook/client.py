"""Call POST /v1/check with a timeout. Fail-safe: any problem -> ASK.

The hook never crashes the host tool and never silently allows: a service that
is down, a timeout, a non-200 status or an unparseable body all return an ASK
decision. A local secret pre-check (in cli.py) can still force BLOCK offline.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8080"
DEFAULT_TIMEOUT = 5.0


def service_url() -> str:
    return os.environ.get("GUARDRAILS_URL", DEFAULT_URL).rstrip("/")


def timeout_seconds() -> float:
    try:
        return float(os.environ.get("GUARDRAILS_TIMEOUT", DEFAULT_TIMEOUT))
    except ValueError:
        return DEFAULT_TIMEOUT


def _failsafe(reason: str) -> dict:
    return {
        "decision": "ASK",
        "check_ids": [],
        "reasons": [{"check_id": None, "decision": "ASK", "source": "fail-safe",
                     "title": reason, "obligations": []}],
        "obligations": [],
        "missing_artefacts": [],
        "_failsafe": True,
    }


def post_check(payload: dict, *, url: str | None = None, timeout: float | None = None,
               opener=urllib.request.urlopen) -> dict:
    """POST the normalised event to /v1/check. Returns the decision dict.

    ``opener`` is injectable for tests. On any error the result is a fail-safe
    ASK decision (``_failsafe: True``).
    """
    base = (url or service_url()).rstrip("/")
    to = timeout if timeout is not None else timeout_seconds()
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/v1/check", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with opener(req, timeout=to) as resp:
            status = getattr(resp, "status", 200)
            body = resp.read().decode("utf-8")
        if status != 200:
            return _failsafe(f"policy service returned HTTP {status}; routed to a human")
        parsed = json.loads(body)
        if not isinstance(parsed, dict) or "decision" not in parsed:
            return _failsafe("policy service returned an unexpected body; routed to a human")
        return parsed
    except (urllib.error.URLError, OSError) as exc:
        return _failsafe(f"policy service unreachable ({exc}); routed to a human")
    except (ValueError, json.JSONDecodeError):
        return _failsafe("policy service returned invalid JSON; routed to a human")
