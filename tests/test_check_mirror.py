"""Phase 1 — Python mirror of policy/check.rego (BLOCK > ASK > WARN > ALLOW).

These mirror the cases in policy/check_test.rego so the decision logic is
verified in pytest even without the opa binary. policy/check.rego is
authoritative; a divergence is a bug.
"""

from aca.check.decide import CheckPolicy, decide_checks


def _policy():
    return CheckPolicy.load()


def test_social_scoring_full_blocks():
    r = decide_checks(["AIA-5-1-c"], _policy(), partial_social=False)
    assert r.decision == "BLOCK"


def test_social_scoring_partial_asks():
    r = decide_checks(["AIA-5-1-c"], _policy(), partial_social=True)
    assert r.decision == "ASK"


def test_secret_blocks():
    r = decide_checks(["SEC-SECRETS"], _policy())
    assert r.decision == "BLOCK"


def test_annex_iii_4a_alone_is_warn():
    r = decide_checks(["AIA-A3-4a"], _policy())
    assert r.decision == "WARN"


def test_cv_bundle_with_related_is_warn():
    r = decide_checks(
        ["AIA-A3-4a"], _policy(),
        related=["GDPR-22", "GDPR-35", "AIA-26-7", "DE-BETRVG-87"],
    )
    assert r.decision == "WARN"
    # Companion article refs are present in reasons.
    ref_ids = {x["check_id"] for x in r.reasons}
    assert {"GDPR-22", "GDPR-35", "AIA-26-7", "DE-BETRVG-87"} <= ref_ids


def test_cv_bundle_solely_automated_escalates_to_ask():
    # GDPR-22 arrives as a primary fired check (caller decided solely-automated).
    r = decide_checks(
        ["AIA-A3-4a", "GDPR-22"], _policy(),
        related=["GDPR-35", "AIA-26-7", "DE-BETRVG-87"],
    )
    assert r.decision == "ASK"


def test_credit_scoring_obligations_include_fria():
    r = decide_checks(["AIA-A3-5b"], _policy())
    assert "fria" in r.obligations


def test_no_checks_allows():
    r = decide_checks([], _policy())
    assert r.decision == "ALLOW"


def test_missing_artefacts_computed_from_use_case():
    use_case = {"artefacts": {"risk_management": "compliance/risk.md", "dpia": None}}
    r = decide_checks(["AIA-A3-4a"], _policy(), use_case=use_case)
    # risk_management is present; dpia + the rest are missing.
    assert "risk_management" not in r.missing_artefacts
    assert "dpia" in r.missing_artefacts
    assert "worker_information" in r.missing_artefacts
