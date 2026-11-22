"""Phase 4 — deploy gate (Python mirror of policy/deploy.rego).

Mirrors the cases in policy/deploy_test.rego so the gate logic is verified in
pytest even without the opa binary. policy/deploy.rego is authoritative; a
divergence is a bug.
"""

from aca.check.deploy import decide_deploy

_OBLIGATIONS = ["risk_management", "dpia", "oversight_plan", "eval_report", "worker_information"]

_ALL_PRESENT = {
    "risk_management": "docs/rm.md",
    "dpia": "docs/dpia.md",
    "oversight_plan": "docs/oversight.md",
    "eval_report": "docs/eval.md",
    "worker_information": "docs/worker-info.md",
}

_TWO_EACH = [
    {"artefact": "*", "approver": "alice"},
    {"artefact": "*", "approver": "bob"},
]


def test_denied_when_artefacts_missing():
    r = decide_deploy({"obligations": _OBLIGATIONS,
                       "artefacts": {"dpia": None, "oversight_plan": None},
                       "approvals": []})
    assert r.decision == "DENY"
    assert "dpia" in r.missing_artefacts
    assert "oversight_plan" in r.missing_artefacts


def test_deny_reasons_name_the_missing_artefacts():
    r = decide_deploy({"obligations": ["dpia", "oversight_plan"],
                       "artefacts": {"dpia": None, "oversight_plan": None},
                       "approvals": []})
    assert "dpia artefact missing" in r.reasons
    assert "oversight_plan artefact missing" in r.reasons


def test_denied_when_only_one_approver():
    r = decide_deploy({"obligations": ["dpia"],
                       "artefacts": {"dpia": "docs/dpia.md"},
                       "approvals": [{"artefact": "dpia", "approver": "alice"}]})
    assert r.decision == "DENY"
    assert "dpia" in r.under_approved


def test_same_person_twice_is_one_approver():
    r = decide_deploy({"obligations": ["dpia"],
                       "artefacts": {"dpia": "docs/dpia.md"},
                       "approvals": [
                           {"artefact": "dpia", "approver": "alice"},
                           {"artefact": "dpia", "approver": "alice"},
                       ]})
    assert r.decision == "DENY"


def test_allowed_when_present_and_two_distinct_approvers():
    r = decide_deploy({"obligations": _OBLIGATIONS,
                       "artefacts": _ALL_PRESENT,
                       "approvals": _TWO_EACH})
    assert r.decision == "ALLOW"


def test_flat_approver_names_apply_to_all():
    r = decide_deploy({"obligations": ["dpia", "oversight_plan"],
                       "artefacts": {"dpia": "a", "oversight_plan": "b"},
                       "approvals": ["alice", "bob"]})
    assert r.decision == "ALLOW"


def test_break_glass_allows_with_justification():
    r = decide_deploy({"obligations": _OBLIGATIONS,
                       "artefacts": {"dpia": None},
                       "approvals": [],
                       "break_glass": {"active": True,
                                       "justification": "incident INC-42 hotfix",
                                       "approver": "ciso"}})
    assert r.decision == "ALLOW"
    assert any("break-glass" in x for x in r.reasons)


def test_break_glass_without_justification_still_denies():
    r = decide_deploy({"obligations": ["dpia"],
                       "artefacts": {"dpia": None},
                       "approvals": [],
                       "break_glass": {"active": True, "justification": "", "approver": "ciso"}})
    assert r.decision == "DENY"


def test_no_obligations_allows():
    r = decide_deploy({"obligations": [], "artefacts": {}, "approvals": []})
    assert r.decision == "ALLOW"
