"""Demo: run the packaged policy service in-process and exercise it (Phase 8).

This is the ``docker compose up`` story without Docker: it starts the same
server the container runs (``python -m aca.guard.api``) on an ephemeral port and
sends /healthz plus three /v1/check calls, printing the decisions. On a machine
with Docker, ``docker compose -f deploy/docker/docker-compose.yml up`` runs the
identical service plus an OPA bundle server.
"""

from __future__ import annotations

import json
import threading
import urllib.request

from aca.guard.api.__main__ import build_server

_CASES = [
    ("social scoring", "Join badge logs, Slack activity and canteen data per employee "
     "into a reliability index and drop the bottom 10% from the bonus pool."),
    ("fraud score", "Compute a fraud risk score on card transactions and flag the riskiest "
     "for manual review."),
    ("secret in a diff", None),
]


def _post(base: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{base}/v1/check", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


def main() -> int:
    httpd = build_server("127.0.0.1", 0, "oss")
    port = httpd.server_address[1]
    base = f"http://127.0.0.1:{port}"
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print("Phase 8 demo — packaged policy service (in-process; same as the container)\n")
    try:
        with urllib.request.urlopen(f"{base}/healthz", timeout=5) as r:
            print(f"GET /healthz -> {json.loads(r.read())}")
        print()
        for name, text in _CASES:
            if name == "secret in a diff":
                payload = {"event": "diff", "diff": 'AWS_ACCESS_KEY_ID = "AKIAXXXXXXXXXXXXXXXX"'}
            else:
                payload = {"event": "prompt", "text": text}
            out = _post(base, payload)
            rules = ", ".join(out.get("check_ids", [])) or "(none)"
            print(f"POST /v1/check [{name}] -> {out['decision']}  rules: {rules}")
    finally:
        httpd.shutdown()
    print("\nWith Docker: docker compose -f deploy/docker/docker-compose.yml up")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
