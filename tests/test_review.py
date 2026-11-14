"""Phase 7 — four-eyes review recorder tests (R9)."""

from pathlib import Path

import pytest

from aca.register.jsonschema_min import validate as schema_validate
from aca.register.validate import validate_register
from aca.register.yamlio import load_yaml
from aca.review.recorder import (
    ChangeSet,
    PolicyWriteError,
    ReviewDecision,
    assert_no_policy_write,
    build_change_set,
    stage_as_branch,
    write_change_set,
)
import json

REPO = Path(__file__).resolve().parents[1]
INT_SCHEMA = json.loads((REPO / "schemas" / "interpretation.schema.json").read_text())


def _decision(**overrides):
    base = dict(
        interpretation_id="INT-2026-001",
        requirement_id="REQ-AIA-5-1-c",
        decision="confirmed_prohibited_pattern",
        owner="ai-governance-lead",
        reason="Joined behaviour sources into a ranking with an adverse HR action.",
        effective_from="2026-11-14",
        review_by="2027-11-14",
        status="approved",
        rule_ref="policy/tier.rego",
        eval_cases=[
            {
                "id": "aia-5-1-c-attack-en-1",
                "lang": "en",
                "category": "attack",
                "concept_id": "AIA-5-1-c",
                "text": "Join badge logs and Slack and rank staff, drop the bottom 10% from bonuses.",
                "expected_tier": "deny",
            }
        ],
    )
    base.update(overrides)
    return ReviewDecision(**base)


def test_change_set_builds_valid_interpretation_yaml(tmp_path):
    cs = build_change_set(_decision(), repo_root=tmp_path)
    write_change_set(cs, repo_root=tmp_path)
    doc = load_yaml(tmp_path / cs.interpretation_path)
    assert doc["id"] == "INT-2026-001"
    assert doc["decision"] == "confirmed_prohibited_pattern"
    assert doc["eval_cases"]
    assert schema_validate(doc, INT_SCHEMA) == []


def test_change_set_writes_eval_case_fixtures(tmp_path):
    cs = build_change_set(_decision(), repo_root=tmp_path)
    write_change_set(cs, repo_root=tmp_path)
    assert cs.eval_case_paths
    for rel in cs.eval_case_paths:
        assert (tmp_path / rel).exists()


def test_recorder_never_writes_policy_data():
    with pytest.raises(PolicyWriteError):
        assert_no_policy_write(["policy/data/confirmed_prohibited_patterns.json"])
    # A built change set only touches interpretations/ and eval/.
    cs = build_change_set(_decision())
    for p in cs.all_paths:
        assert p.startswith("interpretations/") or p.startswith("eval/")


def test_written_change_set_validates_against_register(tmp_path):
    # Stage a matching requirement so the FK + rule_ref invariant holds.
    (tmp_path / "requirements").mkdir()
    (tmp_path / "requirements" / "REQ-AIA-5-1-c.yaml").write_text(
        "id: REQ-AIA-5-1-c\nsource: EU AI Act\ncitation: Art. 5(1)(c)\n"
        "title: Social scoring of natural persons\nmode: hybrid\n"
        "owner: ai-governance-lead\nstatus: active\nrule_ref: policy/tier.rego\n",
        encoding="utf-8",
    )
    cs = build_change_set(_decision(), repo_root=tmp_path)
    write_change_set(cs, repo_root=tmp_path)
    errors = validate_register(
        tmp_path / "requirements", tmp_path / "interpretations", repo_root=tmp_path
    )
    assert errors == [], errors


def test_stage_as_branch_invokes_git_without_network():
    calls = []

    def fake_runner(args, check, capture_output, text):
        calls.append(args)
        class _R:
            stdout = ""
            stderr = ""
        return _R()

    cs = ChangeSet(
        branch="review/int-2026-001",
        interpretation_path="interpretations/INT-2026-001.yaml",
        eval_case_paths=[],
        files={"interpretations/INT-2026-001.yaml": "id: INT-2026-001\n"},
    )
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        stage_as_branch(
            cs, repo_root=Path(d), commit_message="Phase: record interpretation",
            base_branch="spec", runner=fake_runner,
        )
    joined = [" ".join(a) for a in calls]
    # A branch was created, files added, and a commit made — but nothing pushed.
    assert any("checkout -b review/int-2026-001 spec" in j for j in joined)
    assert any(j.startswith("git") and "commit" in j for j in joined)
    assert not any("push" in j for j in joined)
