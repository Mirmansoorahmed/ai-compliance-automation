"""Phase 3 — stage 0 deterministic signal tests (R3.3)."""

from aca.guard.event import Event
from aca.guard.stages.stage0 import run_stage0


def test_detects_social_scoring_hints_en():
    ev = Event(
        text=(
            "Join badge-swipe logs, Slack activity and canteen data per employee, "
            "build a reliability index, and drop the bottom 10% from the bonus pool."
        )
    )
    s = run_stage0(ev)
    assert s.behaviour_hits >= 2
    assert s.score_hits >= 1
    assert s.adverse_hits >= 1


def test_detects_social_scoring_hints_de():
    ev = Event(
        text=(
            "Verbinde Zutritts-Logs, Slack-Aktivität und Kantinendaten pro Mitarbeiter "
            "zu einem Zuverlässigkeitsindex und streiche die untersten 10% aus dem Bonustopf."
        ),
        language="de",
    )
    s = run_stage0(ev)
    assert s.behaviour_hits >= 2
    assert s.score_hits >= 1
    assert s.adverse_hits >= 1


def test_detects_pii_and_secret():
    ev = Event(text="contact alice@example.com; api_key: ABC123")
    s = run_stage0(ev)
    assert s.has_pii and "email" in s.pii_kinds
    assert s.has_secret


def test_benign_fraud_score_has_no_adverse_or_behaviour():
    ev = Event(text="Compute a fraud risk score on card transactions.")
    s = run_stage0(ev)
    assert s.behaviour_hits == 0
    assert s.adverse_hits == 0


def test_data_class_from_tool_metadata():
    ev = Event(text="x", tool={"data_class": "pii"})
    s = run_stage0(ev)
    assert s.data_class == "pii"
