"""Minimal HTTP transport for hybrid adapters (dependency-free).

Hybrid adapters (Prompt Shields, Azure OpenAI judge, Entra) talk to Azure over
HTTPS. The oss profile must not require ``httpx``/``requests``, so this wraps the
standard library ``urllib`` with a timeout and a small, typed error model. The
transport is injectable, so tests feed recorded/mocked responses with no network
and no real credentials.

Error model (used by the fail-safe layer, R8 / Phase 10 rule 3):
    AdapterTimeout      - request exceeded the timeout
    AdapterAuthError    - 401 / 403 (missing or wrong credentials)
    AdapterRateLimited  - 429
    AdapterServerError  - 5xx
    AdapterError        - any other transport failure
All of these cause the adapter to raise; the Guard skips a raising adapter and
the pipeline applies the fail-safe tier (risky/unknown -> ask), never a silent
allow.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class AdapterError(RuntimeError):
    """Base transport error for a hybrid adapter."""


class AdapterTimeout(AdapterError):
    pass


class AdapterAuthError(AdapterError):
    pass


class AdapterRateLimited(AdapterError):
    pass


class AdapterServerError(AdapterError):
    pass


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: dict


class Transport(Protocol):
    def post_json(self, url: str, *, headers: dict, payload: dict, timeout: float) -> HttpResponse:
        ...


def _map_status(status: int, detail: str = "") -> None:
    if status in (401, 403):
        raise AdapterAuthError(f"auth failed ({status}) {detail}".strip())
    if status == 429:
        raise AdapterRateLimited(f"rate limited (429) {detail}".strip())
    if 500 <= status < 600:
        raise AdapterServerError(f"server error ({status}) {detail}".strip())
    if not (200 <= status < 300):
        raise AdapterError(f"unexpected status {status} {detail}".strip())


class UrllibTransport:
    """Real transport over urllib. Used only when hybrid adapters are live."""

    def post_json(self, url: str, *, headers: dict, payload: dict, timeout: float) -> HttpResponse:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # pragma: no cover - network
                status = resp.status
                raw = resp.read().decode("utf-8") or "{}"
                return HttpResponse(status=status, body=json.loads(raw))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            detail = ""
            try:
                detail = exc.read().decode("utf-8")[:200]
            except Exception:
                pass
            _map_status(exc.code, detail)
            raise AdapterError(f"http error {exc.code}") from exc
        except (socket.timeout, TimeoutError) as exc:  # pragma: no cover - network
            raise AdapterTimeout(str(exc)) from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise AdapterTimeout(str(exc)) from exc
            raise AdapterError(str(exc)) from exc


def check_response(resp: HttpResponse) -> dict:
    """Raise the mapped error for a non-2xx response; return the body otherwise."""
    _map_status(resp.status)
    return resp.body
