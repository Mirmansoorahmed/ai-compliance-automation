"""Phase 1 — register cross-file invariants and starter map (R1, R2)."""

from pathlib import Path

import pytest

from aca.register.validate import validate_register
from aca.register.yamlio import load_yaml

REPO = Path(__file__).resolve().parents[1]
REQ_DIR = REPO / "requirements"
INT_DIR = REPO / "interpretations"

STARTER_MODES = {
    "REQ-AIA-5-1-c": "hybrid",
    "REQ-AIA-5-1-f": "hybrid",
    "REQ-AIA-9": "human",
    "REQ-AIA-12": "auto",
    "REQ-AIA-14": "hybrid",
    "REQ-ISO-A-5-3": "auto",
    "REQ-ISO-A-5-14": "hybrid",
    "REQ-ISO-A-5-15": "auto",
    "REQ-ISO-A-5-34": "hybrid",
    "REQ-ISO-A-8-12": "hybrid",
    "REQ-ISO-A-8-15": "auto",
}


def test_real_register_validates_clean():
    errors = validate_register(REQ_DIR, INT_DIR, repo_root=REPO)
    assert errors == [], errors


def test_starter_map_ids_and_modes_present():
    found = {}
    for path in REQ_DIR.glob("*.yaml"):
        doc = load_yaml(path)
        found[doc["id"]] = doc["mode"]
    assert found == STARTER_MODES


def test_titles_are_own_words_not_empty():
    for path in REQ_DIR.glob("*.yaml"):
        doc = load_yaml(path)
        assert isinstance(doc["title"], str) and doc["title"].strip()


# --- cross-file invariants, using synthetic temp registers ---

def _write(dir_: Path, name: str, text: str):
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / name).write_text(text, encoding="utf-8")


def test_rule_ref_without_approved_interpretation_fails(tmp_path):
    req = tmp_path / "requirements"
    inter = tmp_path / "interpretations"
    inter.mkdir()
    _write(
        req,
        "REQ-A.yaml",
        "id: REQ-A\nsource: EU AI Act\ncitation: Art. 5\ntitle: t\n"
        "mode: auto\nowner: o\nstatus: active\nrule_ref: policy/tier.rego\n",
    )
    errors = validate_register(req, inter, repo_root=tmp_path)
    assert any("no approved interpretation" in e for e in errors)


def test_rule_ref_on_human_mode_fails(tmp_path):
    req = tmp_path / "requirements"
    inter = tmp_path / "interpretations"
    inter.mkdir()
    _write(
        req,
        "REQ-A.yaml",
        "id: REQ-A\nsource: EU AI Act\ncitation: Art. 9\ntitle: t\n"
        "mode: human\nowner: o\nstatus: active\nrule_ref: policy/tier.rego\n",
    )
    errors = validate_register(req, inter, repo_root=tmp_path)
    assert any("must be 'auto' or 'hybrid'" in e for e in errors)


def test_interpretation_fk_must_resolve(tmp_path):
    req = tmp_path / "requirements"
    inter = tmp_path / "interpretations"
    req.mkdir()
    _write(
        inter,
        "INT-2026-001.yaml",
        "id: INT-2026-001\nversion: 1\nrequirement_id: REQ-MISSING\n"
        "decision: needs_review\nowner: o\nreason: r\n"
        "effective_from: 2026-01-01\nreview_by: 2027-01-01\nstatus: draft\n",
    )
    errors = validate_register(req, inter, repo_root=tmp_path)
    assert any("does not resolve" in e for e in errors)


def test_confirmed_pattern_requires_approved_status(tmp_path):
    req = tmp_path / "requirements"
    inter = tmp_path / "interpretations"
    _write(
        req,
        "REQ-A.yaml",
        "id: REQ-A\nsource: EU AI Act\ncitation: Art. 5\ntitle: t\n"
        "mode: hybrid\nowner: o\nstatus: active\n",
    )
    _write(
        inter,
        "INT-2026-001.yaml",
        "id: INT-2026-001\nversion: 1\nrequirement_id: REQ-A\n"
        "decision: confirmed_prohibited_pattern\nowner: o\nreason: r\n"
        "effective_from: 2026-01-01\nreview_by: 2027-01-01\nstatus: draft\n",
    )
    errors = validate_register(req, inter, repo_root=tmp_path)
    assert any("requires status 'approved'" in e for e in errors)


def test_rule_ref_with_approved_interpretation_passes(tmp_path):
    req = tmp_path / "requirements"
    inter = tmp_path / "interpretations"
    _write(
        req,
        "REQ-A.yaml",
        "id: REQ-A\nsource: EU AI Act\ncitation: Art. 5\ntitle: t\n"
        "mode: hybrid\nowner: o\nstatus: active\nrule_ref: policy/tier.rego\n",
    )
    _write(
        inter,
        "INT-2026-001.yaml",
        "id: INT-2026-001\nversion: 1\nrequirement_id: REQ-A\n"
        "decision: confirmed_prohibited_pattern\nowner: o\nreason: r\n"
        "effective_from: 2026-01-01\nreview_by: 2027-01-01\n"
        "rule_ref: policy/tier.rego\nstatus: approved\n",
    )
    errors = validate_register(req, inter, repo_root=tmp_path)
    assert errors == [], errors


def test_missing_eval_case_path_fails(tmp_path):
    req = tmp_path / "requirements"
    inter = tmp_path / "interpretations"
    _write(
        req,
        "REQ-A.yaml",
        "id: REQ-A\nsource: EU AI Act\ncitation: Art. 5\ntitle: t\n"
        "mode: hybrid\nowner: o\nstatus: active\n",
    )
    _write(
        inter,
        "INT-2026-001.yaml",
        "id: INT-2026-001\nversion: 1\nrequirement_id: REQ-A\n"
        "decision: needs_review\nowner: o\nreason: r\n"
        "effective_from: 2026-01-01\nreview_by: 2027-01-01\nstatus: draft\n"
        "eval_cases:\n  - eval/cases/does-not-exist.yaml\n",
    )
    errors = validate_register(req, inter, repo_root=tmp_path)
    assert any("does not exist" in e for e in errors)
