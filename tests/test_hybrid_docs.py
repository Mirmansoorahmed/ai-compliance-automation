"""Phase 10 — hybrid docs + default-off guarantees (R15.2, R15.3, R16)."""

from pathlib import Path

from aca.config import load_config

REPO = Path(__file__).resolve().parents[1]
HYBRID_DOC = (REPO / "docs" / "HYBRID.md").read_text(encoding="utf-8")


def test_runbook_documents_budget_alert_prerequisite():
    low = HYBRID_DOC.lower()
    assert "budget alert" in low
    # Neutral wording only — no account-specific credit amount / tenant / plan.
    assert "low-cost azure lab subscription" in low
    for banned in ("azure for students", "$90", "iu tenant"):
        assert banned not in low


def test_runbook_lists_env_vars_and_command():
    for var in (
        "ACA_PROMPT_SHIELDS_ENDPOINT",
        "ACA_PROMPT_SHIELDS_KEY",
        "ACA_AZURE_OPENAI_ENDPOINT",
        "ACA_AZURE_OPENAI_DEPLOYMENT",
        "ACA_ENTRA_TENANT_ID",
    ):
        assert var in HYBRID_DOC
    assert "make hybrid-eval" in HYBRID_DOC


def test_runbook_states_prompt_shields_not_a_verdict():
    low = HYBRID_DOC.lower()
    assert "not a legal" in low or "not an authorization" in low
    assert "to be measured" in low


def test_default_config_keeps_hybrid_off():
    cfg = load_config()  # default
    assert cfg.profile == "oss"
    assert cfg.adapters == ("local_embeddings",)
    assert cfg.judge_enabled is False


def test_hybrid_profile_judge_off_by_default():
    cfg = load_config("hybrid")
    assert cfg.judge_enabled is False
