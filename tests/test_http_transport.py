"""Phase 10 — HTTP transport error mapping (fail-safe foundation)."""

import pytest

from aca.guard.adapters.http_transport import (
    AdapterAuthError,
    AdapterError,
    AdapterRateLimited,
    AdapterServerError,
    HttpResponse,
    check_response,
)


def test_2xx_returns_body():
    assert check_response(HttpResponse(200, {"ok": True})) == {"ok": True}


@pytest.mark.parametrize("status,exc", [
    (401, AdapterAuthError),
    (403, AdapterAuthError),
    (429, AdapterRateLimited),
    (500, AdapterServerError),
    (503, AdapterServerError),
    (418, AdapterError),
])
def test_error_statuses_map_to_typed_errors(status, exc):
    with pytest.raises(exc):
        check_response(HttpResponse(status, {}))
