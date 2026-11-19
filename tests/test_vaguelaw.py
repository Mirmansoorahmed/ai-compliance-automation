"""Phase 5b — vague-law classifier: backends, routing, questions, eval, Jev guard.

Tests use the deterministic FakeBackend (or the offline hashed LocalBackend)
only. The closed Jev backend is never constructed — a test asserts it refuses to
enable without the operator's explicit env + synthetic-data acknowledgement.
"""

import pytest

from aca.catalog.loader import load_catalog
from aca.vaguelaw import FakeBackend, LocalBackend
from aca.vaguelaw.backend import Answer, Question
from aca.vaguelaw.classify import ACT, ASK, NO, classify
from aca.vaguelaw.eval import evaluate
from aca.vaguelaw.questions import load_questions, question_by_id


# --- question sets ------------------------------------------------------------

def test_questions_load_and_reference_catalog_ids():
    questions = load_questions()
    assert questions
    ids = {c["id"] for c in load_catalog()["checks"]}
    for q in questions:
        assert q.id in ids, f"question {q.id} not a catalog id"
        assert 0.0 < q.act_threshold <= 1.0
        assert q.question


def test_question_by_id():
    q = question_by_id("GDPR-22")
    assert q is not None and q.act_label == "ASK"


# --- routing (deterministic, scripted FakeBackend) ---------------------------

def _q(qid="Q", act="BLOCK", thr=0.6):
    return Question(id=qid, question="?", act_label=act, act_threshold=thr, ask_below=thr)


def test_route_act_when_confident_yes():
    be = FakeBackend(script={"Q": 0.9})
    r = classify("state", [_q()], be)[0]
    assert r.route == ACT
    assert r.act_label == "BLOCK"


def test_route_no_when_confident_no():
    be = FakeBackend(script={"Q": 0.1})
    r = classify("state", [_q()], be)[0]
    assert r.route == NO


def test_route_ask_when_uncertain():
    be = FakeBackend(script={"Q": 0.5})
    r = classify("state", [_q()], be)[0]
    assert r.route == ASK


def test_missing_answer_routes_to_ask():
    class _Empty:
        name = "empty"
        def decide(self, state, questions):
            return []
    r = classify("state", [_q()], _Empty())[0]
    assert r.route == ASK


# --- local backend (offline hashed) ------------------------------------------

def test_local_backend_runs_offline():
    be = LocalBackend()
    qs = load_questions()
    answers = be.decide("The model alone approves or rejects the loan with no human review.", qs)
    assert len(answers) == len(qs)
    for a in answers:
        assert 0.0 <= a.p_yes <= 1.0
        assert a.backend.startswith("local:")


# --- eval harness -------------------------------------------------------------

def test_eval_runs_with_fake_backend():
    # Script confident, correct answers so the smoke accuracy is well-defined.
    be = FakeBackend(script={"AIA-6-3": 0.9, "GDPR-22": 0.9})
    res = evaluate(be)
    assert res.n >= 1
    # accuracy/ece/ask_rate are floats or None; the note marks it smoke.
    assert res.ask_rate is not None
    assert "smoke" in res.note.lower()


# --- Jev backend is disabled by default --------------------------------------

def test_jev_backend_disabled_without_env(monkeypatch):
    monkeypatch.delenv("VAGUELAW_JEV_ENABLED", raising=False)
    monkeypatch.delenv("VAGUELAW_JEV_API_KEY", raising=False)
    from aca.vaguelaw.jev_backend import JevBackend, JevBackendDisabled
    with pytest.raises(JevBackendDisabled):
        JevBackend()


def test_jev_backend_requires_key_and_synthetic_ack(monkeypatch):
    from aca.vaguelaw.jev_backend import JevBackend, JevBackendDisabled
    monkeypatch.setenv("VAGUELAW_JEV_ENABLED", "1")
    monkeypatch.delenv("VAGUELAW_JEV_API_KEY", raising=False)
    with pytest.raises(JevBackendDisabled):
        JevBackend(synthetic_ok=True)  # no key
    monkeypatch.setenv("VAGUELAW_JEV_API_KEY", "fake-synthetic-key")
    with pytest.raises(JevBackendDisabled):
        JevBackend(synthetic_ok=False)  # synthetic not acknowledged
