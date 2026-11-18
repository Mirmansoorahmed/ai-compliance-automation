"""Phase 1 — POST /v1/check end to end (3 fixtures + secret diff + fail-safe).

Uses the hashed-fallback embedder (no model download). /v1/labels must keep
working alongside /v1/check.
"""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from aca.check.service import CheckService
from aca.config import load_config
from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.api.app import API_VERSION, LabelService, make_handler
from aca.guard.embeddings import HashedEmbedder
from aca.guard.event import Event
from aca.guard.service import SemanticGuard
from aca.usecase.registry import load_registry


def _guard():
    return SemanticGuard(adapters=[LocalEmbeddingsAdapter(embedder=HashedEmbedder(dim=256))])


def _check_service():
    return CheckService(guard=_guard(), use_cases=load_registry())


SOCIAL = ("Join badge logs, Slack activity and canteen data per employee into a "
          "reliability index and drop the bottom 10% from the bonus pool.")
CV = "Build a CV screening tool that scores applicants and shortlists the top 20."
FRAUD = "Compute a fraud risk score on card transactions and flag the riskiest for manual review."
SECRET_DIFF = '+AZURE_KEY = "abc8Q~verylongsecretvalue012345678901234"'


def test_cv_screening_warns_with_obligations():
    svc = _check_service()
    out = svc.check({"event": "prompt", "text": CV, "use_case": "uc-hr-cv-screening"})
    assert out["decision"] == "WARN"
    assert "AIA-A3-4a" in out["check_ids"]
    assert "worker_information" in out["obligations"]
    # All six artefacts are null in the fixture -> all missing.
    assert set(out["missing_artefacts"]) == set(out["obligations"])


def test_social_scoring_blocks():
    svc = _check_service()
    out = svc.check({"event": "prompt", "text": SOCIAL, "use_case": "uc-hr-reliability-index"})
    assert out["decision"] == "BLOCK"
    assert "AIA-5-1-c" in out["check_ids"]


def test_fraud_score_allows():
    svc = _check_service()
    out = svc.check({"event": "prompt", "text": FRAUD, "use_case": "uc-fraud-transaction-score"})
    assert out["decision"] == "ALLOW"
    assert out["check_ids"] == []


def test_secret_diff_blocks():
    svc = _check_service()
    out = svc.check({"event": "diff", "text": "", "artefact": SECRET_DIFF})
    assert out["decision"] == "BLOCK"
    assert "SEC-SECRETS" in out["check_ids"]


def test_fail_safe_to_ask_on_guard_error():
    class _Boom:
        def label_with_health(self, event):
            raise RuntimeError("guard down")

    svc = CheckService(guard=_Boom(), use_cases=load_registry())
    out = svc.check({"event": "prompt", "text": CV, "use_case": "uc-hr-cv-screening"})
    assert out["decision"] == "ASK"


def test_reasons_carry_article_refs():
    svc = _check_service()
    out = svc.check({"event": "prompt", "text": CV, "use_case": "uc-hr-cv-screening"})
    ref_ids = {r["check_id"] for r in out["reasons"]}
    assert {"AIA-A3-4a", "GDPR-22", "GDPR-35", "AIA-26-7", "DE-BETRVG-87"} <= ref_ids
    for r in out["reasons"]:
        assert r["source"]  # every reason names a legal source


def test_labels_endpoint_still_works_and_check_round_trip():
    label_svc = LabelService(load_config("oss"))  # fixture mode
    check_svc = _check_service()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(label_svc, check_svc))
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        # /v1/labels still works.
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/{API_VERSION}/labels",
            data=json.dumps({"fixture": "default", "text": "x"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            body = json.loads(r.read().decode())
        assert "labels" in body

        # /v1/check works.
        req2 = urllib.request.Request(
            f"http://127.0.0.1:{port}/{API_VERSION}/check",
            data=json.dumps({"event": "prompt", "text": SOCIAL, "use_case": "uc-hr-reliability-index"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req2, timeout=5) as r:
            body2 = json.loads(r.read().decode())
        assert body2["decision"] == "BLOCK"
        assert body2["api_version"] == API_VERSION
    finally:
        httpd.shutdown()


def test_response_does_not_echo_raw_prompt():
    svc = _check_service()
    secret_text = "UNIQUE-RAW-PROMPT-TOKEN-998877"
    out = svc.check({"event": "prompt", "text": secret_text + " " + FRAUD,
                     "use_case": "uc-fraud-transaction-score"})
    assert secret_text not in json.dumps(out)
