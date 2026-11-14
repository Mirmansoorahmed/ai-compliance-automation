"""Phase 4 — stage S session context tests (R3.7)."""

import pytest

from aca.guard.stages.stage_s import SessionContext


def test_stores_labels_only_not_raw_text():
    ctx = SessionContext()
    with pytest.raises(ValueError):
        ctx.add("subj-1", {"concept_id": "AIA-5-1-c", "text": "raw prompt body"})


def test_summary_returns_no_prompt_text():
    ctx = SessionContext()
    ctx.add("subj-1", {"concept_id": "AIA-5-1-c", "elements_met": ["x"], "confidence": 0.4})
    summary = ctx.summary("subj-1")
    assert summary == [{"concept_id": "AIA-5-1-c", "elements_met": ["x"], "confidence": 0.4}]
    for entry in summary:
        assert "text" not in entry and "prompt" not in entry


def test_ttl_expiry_drops_old_labels():
    ctx = SessionContext(ttl_seconds=10)
    ctx.add("subj-1", {"concept_id": "C", "elements_met": ["a"], "confidence": 0.3}, now=1000.0)
    # Query far in the future -> expired.
    assert ctx.summary("subj-1", now=2000.0) == []


def test_salami_accumulates_elements_across_turns():
    ctx = SessionContext(ttl_seconds=900)
    ctx.add("subj-1", {"concept_id": "AIA-5-1-c", "elements_met": ["person_identifiable_behaviour_join"], "confidence": 0.3}, now=1000.0)
    ctx.add("subj-1", {"concept_id": "AIA-5-1-c", "elements_met": ["aggregated_score_or_ranking"], "confidence": 0.3}, now=1001.0)
    ctx.add("subj-1", {"concept_id": "AIA-5-1-c", "elements_met": ["adverse_action"], "confidence": 0.3}, now=1002.0)
    acc = ctx.accumulated_elements("subj-1", "AIA-5-1-c", now=1003.0)
    assert acc == {
        "person_identifiable_behaviour_join",
        "aggregated_score_or_ranking",
        "adverse_action",
    }


def test_subjects_are_isolated():
    ctx = SessionContext()
    ctx.add("subj-1", {"concept_id": "C", "elements_met": ["a"], "confidence": 0.1})
    assert ctx.summary("subj-2") == []
