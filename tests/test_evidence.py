"""Phase 6 — evidence span tests (R10).

Asserts the decision-record v1 fields are present, the subject is pseudonymised,
args are reduced to names/count/hashes, no clear identity or raw body appears,
and the file exporter writes one JSON span per decision.
"""

import json

import pytest

from aca.guard.evidence.emitter import EvidenceEmitter, FileSpanExporter, build_emitter
from aca.guard.evidence.record import REQUIRED_FIELDS, build_decision_record
from aca.guard.evidence.redact import (
    assert_no_forbidden_fields,
    redact_args,
    subject_pseudonym,
)


def _record(**overrides):
    base = dict(
        tier="deny",
        subject_id="alice@nordpay.example",
        resource="hr.scoring_job",
        action="run",
        labels=[{"concept_id": "AIA-5-1-c", "confidence": 0.9, "elements_met": ["a", "b", "c"]}],
        bundle_revision="bundle-abc123",
        groups=["g-hr"],
        site="berlin",
        args={"query": "SELECT ...", "limit": 10},
        latency_ms=12.3,
        approver_ids=["bob@nordpay.example", "carol@nordpay.example"],
    )
    base.update(overrides)
    return build_decision_record(**base)


def test_all_required_fields_present():
    rec = _record()
    assert rec.missing_fields() == []
    for f in REQUIRED_FIELDS:
        assert f in rec.attributes


def test_pep_is_semantic_and_allowed_derived_from_tier():
    assert _record(tier="deny").attributes["pep"] == "semantic"
    assert _record(tier="deny").attributes["allowed"] is False
    assert _record(tier="ask").attributes["allowed"] is False
    assert _record(tier="allow").attributes["allowed"] is True


def test_subject_is_pseudonymised_not_clear():
    rec = _record()
    subj = rec.attributes["subject_pseudonym"]
    assert subj.startswith("subj-")
    assert "alice@nordpay.example" not in json.dumps(rec.attributes)


def test_approvers_pseudonymised():
    rec = _record()
    for a in rec.attributes["approver_pseudonyms"]:
        assert a.startswith("subj-")
    assert "bob@nordpay.example" not in json.dumps(rec.attributes)


def test_args_reduced_to_names_count_hashes_no_raw_values():
    rec = _record()
    args = rec.attributes["args"]
    assert set(args) == {"names", "count", "hashes"}
    assert args["count"] == 2
    assert args["names"] == ["limit", "query"]
    # The raw SQL value must not appear anywhere in the span.
    assert "SELECT ..." not in json.dumps(rec.attributes)
    # Each hash is a 64-char hex digest.
    for h in args["hashes"].values():
        assert len(h) == 64


def test_forbidden_fields_rejected():
    with pytest.raises(ValueError):
        assert_no_forbidden_fields({"role": "admin"})
    with pytest.raises(ValueError):
        assert_no_forbidden_fields({"prompt_body": "secret"})


def test_pseudonym_is_stable_and_salted():
    a = subject_pseudonym("x", salt="s1")
    b = subject_pseudonym("x", salt="s1")
    c = subject_pseudonym("x", salt="s2")
    assert a == b          # stable
    assert a != c          # salt changes the pseudonym


def test_redact_args_empty():
    assert redact_args(None) == {"names": [], "count": 0, "hashes": {}}


def test_file_exporter_writes_one_json_span_per_decision(tmp_path):
    path = tmp_path / "spans.jsonl"
    emitter = EvidenceEmitter(FileSpanExporter(path))
    emitter.emit(
        tier="deny", subject_id="s1", resource="r", action="a",
        labels=[], bundle_revision="b1",
    )
    emitter.emit(
        tier="allow", subject_id="s2", resource="r", action="a",
        labels=[], bundle_revision="b1",
    )
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["span_name"] == "semantic_guard.decision"
    assert first["attributes"]["tier"] == "deny"


def test_build_emitter_file_roundtrip(tmp_path):
    exporter = FileSpanExporter(tmp_path / "spans.jsonl")
    emitter = EvidenceEmitter(exporter)
    rec = emitter.emit(
        tier="four-eyes", subject_id="s1", resource="r", action="a",
        labels=[{"concept_id": "AIA-5-1-c", "confidence": 0.85}], bundle_revision="b1",
    )
    all_spans = exporter.read_all()
    assert len(all_spans) == 1
    assert all_spans[0]["attributes"]["decision_id"] == rec.decision_id


def test_build_emitter_rejects_unknown_exporter():
    with pytest.raises(ValueError):
        build_emitter("carrier-pigeon")
