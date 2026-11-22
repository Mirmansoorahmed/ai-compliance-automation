"""Phase 8 — deployable package: server entry + manifest/compose/Dockerfile sanity.

The server entry is exercised in-process (ThreadingHTTPServer on an ephemeral
port). Docker/compose/OPA are not available in the sandbox, so those files are
checked for well-formedness only; building and running them is an owner step.
"""

import json
import threading
import urllib.request
from pathlib import Path

import pytest

from aca.guard.api.__main__ import build_server

_ROOT = Path(__file__).resolve().parents[1]

SOCIAL = ("Join badge logs, Slack activity and canteen data per employee into a "
          "reliability index and drop the bottom 10% from the bonus pool.")


@pytest.fixture(scope="module")
def server():
    httpd = build_server("127.0.0.1", 0, "oss")
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()


def test_healthz(server):
    with urllib.request.urlopen(f"{server}/healthz", timeout=5) as r:
        body = json.loads(r.read())
    assert body["status"] == "ok"


def test_check_social_blocks(server):
    req = urllib.request.Request(
        f"{server}/v1/check",
        data=json.dumps({"event": "prompt", "text": SOCIAL}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        body = json.loads(r.read())
    assert body["decision"] == "BLOCK"


def test_bundle_manifest_well_formed():
    data = json.loads((_ROOT / "policy" / ".manifest").read_text())
    assert "compliance" in data["roots"]
    assert data["revision"]


def test_dockerfile_present_and_runs_module():
    text = (_ROOT / "deploy" / "docker" / "Dockerfile").read_text()
    assert "python3" in text and "aca.guard.api" in text
    assert "USER guardrails" in text  # non-root


def test_compose_has_policy_service_and_opa():
    text = (_ROOT / "deploy" / "docker" / "docker-compose.yml").read_text()
    assert "policy-service:" in text
    assert "opa:" in text
    assert "8080:8080" in text


def test_release_workflow_is_tag_gated_and_keyless():
    text = (_ROOT / ".github" / "workflows" / "release.yml").read_text()
    assert 'tags:' in text and 'v*' in text
    assert "id-token: write" in text  # keyless cosign OIDC
    assert "cosign sign" in text


def test_azure_bicep_pins_germany_west_central():
    text = (_ROOT / "deploy" / "azure" / "containerapp.bicep").read_text()
    assert "germanywestcentral" in text
