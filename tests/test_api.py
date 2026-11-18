"""Phase 5 — label API and fixture mode tests (R7).

Exercises the LabelService directly and over a real HTTP round-trip on a
loopback port using only the standard library.
"""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from aca.config import load_config
from aca.guard.api.app import API_VERSION, LabelService, make_handler


def test_fixture_mode_returns_committed_labels():
    svc = LabelService(load_config("oss"))  # oss has fixture_mode = true
    resp = svc.labels_for({"text": "anything", "fixture": "default"})
    assert resp["api_version"] == API_VERSION
    assert resp["source"] == "fixture"
    assert isinstance(resp["labels"], list)


def test_fixture_mode_needs_no_network_or_live_guard():
    # LabelService in fixture mode must not require building a live Guard.
    svc = LabelService(load_config("oss"))
    assert svc._guard is None
    resp = svc.labels_for({"fixture": "default"})
    assert "labels" in resp


def test_response_does_not_echo_raw_text():
    svc = LabelService(load_config("oss"))
    secret = "SENSITIVE PROMPT BODY 12345"
    resp = svc.labels_for({"text": secret, "fixture": "default"})
    assert secret not in json.dumps(resp)


def test_live_mode_uses_guard_and_returns_labels():
    cfg = load_config("oss")
    # Force live mode by overriding fixture flag via a tiny shim.
    from dataclasses import replace

    live_cfg = replace(cfg, fixture_mode=False)
    svc = LabelService(live_cfg)
    resp = svc.labels_for({"text": "compute a fraud risk score on transactions"})
    assert resp["source"] == "live"
    assert any(l["concept_id"] == "AIA-5-1-c" for l in resp["labels"])
    for label in resp["labels"]:
        assert "tier" not in label and "decision" not in label


def test_http_round_trip():
    svc = LabelService(load_config("oss"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(svc))
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/{API_VERSION}/labels",
            data=json.dumps({"fixture": "default", "text": "x"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            body = json.loads(r.read().decode("utf-8"))
        assert body["api_version"] == API_VERSION
        assert "labels" in body

        # Unknown path -> 404.
        bad = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/nope",
            data=b"{}",
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(bad, timeout=5)
        assert ei.value.code == 404
    finally:
        httpd.shutdown()
