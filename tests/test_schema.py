"""Phase 1 — JSON Schema validation tests (R1.2, R2.2)."""

import json
from pathlib import Path

from aca.register.jsonschema_min import validate

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def _schema(name):
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_valid_requirement_passes():
    doc = {
        "id": "REQ-AIA-5-1-c",
        "source": "EU AI Act",
        "citation": "Art. 5(1)(c)",
        "title": "Social scoring of natural persons",
        "mode": "hybrid",
        "owner": "ai-governance-lead",
        "status": "active",
    }
    assert validate(doc, _schema("requirement.schema.json")) == []


def test_missing_required_field_fails():
    doc = {"id": "REQ-X", "source": "EU AI Act"}
    errors = validate(doc, _schema("requirement.schema.json"))
    assert any("missing required field" in e for e in errors)


def test_bad_enum_fails():
    doc = {
        "id": "REQ-X",
        "source": "EU AI Act",
        "citation": "Art. 5",
        "title": "x",
        "mode": "sometimes",  # invalid
        "owner": "o",
        "status": "active",
    }
    errors = validate(doc, _schema("requirement.schema.json"))
    assert any("not in enum" in e for e in errors)


def test_unknown_field_fails_additional_properties():
    doc = {
        "id": "REQ-X",
        "source": "EU AI Act",
        "citation": "Art. 5",
        "title": "x",
        "mode": "auto",
        "owner": "o",
        "status": "active",
        "surprise": 1,
    }
    errors = validate(doc, _schema("requirement.schema.json"))
    assert any("unexpected field" in e for e in errors)


def test_valid_interpretation_passes():
    doc = {
        "id": "INT-2026-001",
        "version": 1,
        "requirement_id": "REQ-AIA-5-1-c",
        "decision": "confirmed_prohibited_pattern",
        "owner": "ai-governance-lead",
        "reason": "clear joined-behaviour scoring with adverse HR action",
        "effective_from": "2026-11-14",
        "review_by": "2027-11-14",
        "status": "approved",
    }
    assert validate(doc, _schema("interpretation.schema.json")) == []


def test_bad_date_format_fails():
    doc = {
        "id": "INT-2026-001",
        "version": 1,
        "requirement_id": "REQ-AIA-5-1-c",
        "decision": "needs_review",
        "owner": "o",
        "reason": "r",
        "effective_from": "14/11/2026",  # not YYYY-MM-DD
        "review_by": "2027-11-14",
        "status": "draft",
    }
    errors = validate(doc, _schema("interpretation.schema.json"))
    assert any("YYYY-MM-DD" in e for e in errors)
