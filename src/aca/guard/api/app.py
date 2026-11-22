"""Versioned HTTP label API — POST /v1/labels (R7).

Built on the standard library ``http.server`` so the oss profile needs no web
framework. The gateway (PEP) calls this on the slow path with tool metadata, a
session-label summary, and in-memory classification text. The response is the
label schema; this endpoint never returns a verdict (OPA decides).

Fixture mode (``config.api.fixture_mode``) returns committed labels from
``fixtures/`` so demos and CI run with no live gateway and no cloud call (R7.3).

Privacy: raw prompt/argument bodies from the request are not persisted (R7.4).
The server keeps request text in memory only for the duration of the call.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from aca.config import Config, load_config
from aca.guard.event import Event
from aca.guard.service import SemanticGuard

API_VERSION = "v1"
_FIXTURE_DIR = Path(__file__).resolve().parents[4] / "fixtures"


class LabelService:
    """Core request handler, independent of the HTTP transport (easy to test)."""

    def __init__(self, config: Config | None = None, *, guard: SemanticGuard | None = None,
                 fixture_dir: Path | None = None) -> None:
        self.config = config or load_config()
        self._fixture_dir = fixture_dir or _FIXTURE_DIR
        # In fixture mode we do not build a live Guard unless asked.
        self._guard = guard
        if self._guard is None and not self.config.fixture_mode:
            self._guard = SemanticGuard(self.config)

    def _event_from_request(self, payload: dict) -> Event:
        return Event(
            text=payload.get("text", ""),
            tool=payload.get("tool", {}),
            artefact=payload.get("artefact", ""),
            language=payload.get("language"),
            session_labels=payload.get("session_labels", []),
        )

    def labels_for(self, payload: dict) -> dict:
        if self.config.fixture_mode:
            labels = self._fixture_labels(payload)
            source = "fixture"
        else:
            labels = self._guard.label(self._event_from_request(payload))
            source = "live"
        # Response carries labels only; raw request text is never echoed back
        # or stored.
        return {"api_version": API_VERSION, "source": source, "labels": labels}

    def _fixture_labels(self, payload: dict) -> list[dict]:
        name = payload.get("fixture", "default")
        path = self._fixture_dir / f"{name}.json"
        if not path.exists():
            path = self._fixture_dir / "default.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("labels", [])


def make_handler(service: LabelService, check_service=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence default logging
            pass

        def _send(self, code: int, body: dict):
            payload = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _read_json(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw.decode("utf-8") or "{}")

        def do_POST(self):
            path = self.path.rstrip("/")
            if path == f"/{API_VERSION}/labels":
                try:
                    payload = self._read_json()
                except json.JSONDecodeError:
                    self._send(400, {"error": "invalid JSON"})
                    return
                try:
                    self._send(200, service.labels_for(payload))
                except Exception as exc:  # pragma: no cover - defensive
                    self._send(500, {"error": str(exc)})
                return

            if path == f"/{API_VERSION}/check":
                if check_service is None:
                    self._send(404, {"error": "not found"})
                    return
                try:
                    payload = self._read_json()
                except json.JSONDecodeError:
                    self._send(400, {"error": "invalid JSON"})
                    return
                # The check service is fail-safe internally (errors -> ASK).
                self._send(200, {"api_version": API_VERSION, **check_service.check(payload)})
                return

            self._send(404, {"error": "not found"})

        def do_GET(self):
            if self.path.rstrip("/") == "/healthz":
                self._send(200, {"status": "ok", "api_version": API_VERSION})
            else:
                self._send(404, {"error": "not found"})

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8080, config: Config | None = None):  # pragma: no cover
    from aca.check.service import CheckService
    from aca.guard.service import SemanticGuard

    service = LabelService(config)
    guard = SemanticGuard(config) if config and not config.fixture_mode else None
    check_service = CheckService(guard=guard)
    httpd = ThreadingHTTPServer((host, port), make_handler(service, check_service))
    httpd.serve_forever()
