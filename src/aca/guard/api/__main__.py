"""Run the policy service: ``python -m aca.guard.api`` (Phase 8 container entry).

Serves POST /v1/labels and POST /v1/check with a live Guard wired for the oss
profile (hashed-fallback embedder when no model is installed, the real MiniLM
model when the ``embeddings`` extra is present). Binds to 0.0.0.0 inside a
container by default. Host/port/profile come from the environment:

    GUARDRAILS_HOST   (default 0.0.0.0)
    GUARDRAILS_PORT   (default 8080)
    ACA_PROFILE       (default oss)
"""

from __future__ import annotations

import os
from http.server import ThreadingHTTPServer

from aca.check.service import CheckService
from aca.config import load_config
from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.api.app import LabelService, make_handler
from aca.guard.embeddings import build_embedder
from aca.guard.service import SemanticGuard


def build_server(host: str, port: int, profile: str) -> ThreadingHTTPServer:
    config = load_config(profile)
    embedder = build_embedder(allow_hashed_fallback=True, dim=256)
    guard = SemanticGuard(adapters=[LocalEmbeddingsAdapter(embedder=embedder, dim=256)])
    check = CheckService(guard=guard)
    label = LabelService(config)
    return ThreadingHTTPServer((host, port), make_handler(label, check))


def main() -> int:  # pragma: no cover - process entry
    host = os.environ.get("GUARDRAILS_HOST", "0.0.0.0")
    port = int(os.environ.get("GUARDRAILS_PORT", "8080"))
    profile = os.environ.get("ACA_PROFILE", "oss")
    httpd = build_server(host, port, profile)
    print(f"policy service listening on {host}:{port} (profile={profile})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:  # graceful stop
        httpd.shutdown()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
