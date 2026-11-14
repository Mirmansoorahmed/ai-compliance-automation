"""Phase 3 — label schema tests (R3.1, R3.2, R3.8)."""

import pytest

from aca.guard.labels.schema import Label, is_verdict_free, validate_label


def test_label_builds_and_serialises():
    label = Label(
        concept_id="AIA-5-1-c",
        confidence=0.9,
        elements_met=["join", "score", "adverse"],
        evidence_refs=["stage0:behaviour_hits=3"],
        detector_versions={"stage0": "stage0/0.1.0"},
        pattern_id="AIA-5-1-c/joined-behaviour-adverse-action",
    )
    d = label.to_dict()
    assert d["concept_id"] == "AIA-5-1-c"
    assert d["pattern_id"]
    assert validate_label(d) == []


def test_null_pattern_id_omitted():
    label = Label(concept_id="AIA-5-1-c", confidence=0.1)
    assert "pattern_id" not in label.to_dict()


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValueError):
        Label(concept_id="X", confidence=1.5)


def test_verdict_field_is_rejected():
    bad = {"concept_id": "X", "confidence": 0.5, "tier": "deny"}
    assert not is_verdict_free(bad)
    errors = validate_label(bad)
    assert any("verdict" in e for e in errors)


def test_detector_versions_present_for_reproducibility():
    label = Label(concept_id="X", confidence=0.5, detector_versions={"stage1": "v"})
    assert label.to_dict()["detector_versions"] == {"stage1": "v"}


def test_partial_pattern_and_total_are_signals_not_verdicts():
    label = Label(
        concept_id="AIA-5-1-c", confidence=0.4,
        elements_met=["join", "score"], elements_total=3, partial_pattern=True,
    )
    d = label.to_dict()
    assert d["partial_pattern"] is True
    assert d["elements_total"] == 3
    assert validate_label(d) == []  # partial_pattern/elements_total are not verdicts


def test_partial_and_total_omitted_when_default():
    d = Label(concept_id="X", confidence=0.1).to_dict()
    assert "partial_pattern" not in d
    assert "elements_total" not in d
