"""Phase 1 — use-case.yaml schema + validator + fixtures."""

from pathlib import Path

from aca.usecase.registry import load_registry
from aca.usecase.validate import validate_use_case, validate_use_case_file

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "fixtures" / "use-cases"


def test_three_fixtures_present_and_valid():
    reg = load_registry(FIXTURES)
    assert set(reg) == {
        "uc-hr-cv-screening",
        "uc-hr-reliability-index",
        "uc-fraud-transaction-score",
    }
    for path in FIXTURES.glob("*.yaml"):
        assert validate_use_case_file(path) == [], path.name


def test_missing_required_field_fails():
    errors = validate_use_case({"id": "uc-x"})
    assert any("missing required field" in e for e in errors)


def test_bad_id_pattern_fails():
    doc = {
        "id": "CV_Screening", "title": "t", "intended_purpose": "p",
        "ai_system": True, "role": "deployer", "annex_iii": [], "owner": "o",
    }
    errors = validate_use_case(doc)
    assert any("does not match pattern" in e for e in errors)


def test_bad_role_enum_fails():
    doc = {
        "id": "uc-x", "title": "t", "intended_purpose": "p",
        "ai_system": True, "role": "operator", "annex_iii": [], "owner": "o",
    }
    errors = validate_use_case(doc)
    assert any("not in enum" in e for e in errors)


def test_art6_3_exception_with_profiling_is_invalid():
    doc = {
        "id": "uc-x", "title": "t", "intended_purpose": "p",
        "ai_system": True, "role": "deployer", "annex_iii": ["4(a)"], "owner": "o",
        "art6_3_exception": True, "profiling": True,
    }
    errors = validate_use_case(doc)
    assert any("art6_3_exception cannot be true while profiling is true" in e for e in errors)


def test_cv_fixture_declares_annex_iii_4a():
    reg = load_registry(FIXTURES)
    assert reg["uc-hr-cv-screening"]["annex_iii"] == ["4(a)"]
