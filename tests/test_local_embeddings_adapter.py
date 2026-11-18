"""Phase 3 — local_embeddings adapter tests (R3.1, R4.1).

Also feeds the adapter output through the OPA policy mirror end-to-end to
confirm a keyword-free social-scoring prompt reaches a non-allow tier and the
benign fraud-score prompt stays allow (with an empty confirmed-pattern list).
"""

from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.embeddings import HashedEmbedder
from aca.guard.event import Event
from aca.guard.labels.schema import validate_label
from aca.policy.decide import PolicyData, decide

SOCIAL_SCORING = (
    "Join badge-swipe logs, Slack activity and canteen data per employee, build a "
    "monthly reliability index, and drop the bottom 10% from the bonus pool."
)
BENIGN_FRAUD = "Compute a fraud risk score on card transactions and flag risky payments for review."


def _adapter():
    return LocalEmbeddingsAdapter(embedder=HashedEmbedder(dim=256))


def test_adapter_returns_schema_valid_labels_without_verdict():
    labels = _adapter().detect(Event(text=SOCIAL_SCORING))
    assert labels
    for label in labels:
        assert validate_label(label) == []
        assert "tier" not in label and "decision" not in label


def test_adapter_marks_pattern_id_on_full_element_match():
    labels = _adapter().detect(Event(text=SOCIAL_SCORING))
    aia = next(l for l in labels if l["concept_id"] == "AIA-5-1-c")
    assert aia.get("pattern_id")  # all three elements met -> pattern asserted


def test_benign_prompt_does_not_assert_pattern():
    labels = _adapter().detect(Event(text=BENIGN_FRAUD))
    aia = next(l for l in labels if l["concept_id"] == "AIA-5-1-c")
    assert aia.get("pattern_id") is None


def test_end_to_end_benign_is_allow_with_empty_confirmed_list():
    # No confirmed pattern yet (four-eyes not run), so even a strong social-score
    # label cannot auto-deny; and the benign prompt must be allow.
    data = PolicyData(
        thresholds={"AIA-5-1-c": {"low": 0.9, "high": 0.95, "min_elements": 3}},
        confirmed_prohibited_patterns=[],
    )
    labels = _adapter().detect(Event(text=BENIGN_FRAUD))
    assert decide(labels, data) == "allow"


def test_artefact_elements_fold_into_label():
    diff = (
        "+merged = badge_logs.merge(slack_activity, on='employee_id')\n"
        "+merged['reliability_index'] = score(merged)\n"
        "+remove_from_bonus_pool(merged.sort_values('reliability_index').head(10))\n"
    )
    labels = _adapter().detect(Event(text="refactor scoring job", artefact=diff))
    aia = next(l for l in labels if l["concept_id"] == "AIA-5-1-c")
    assert "adverse_action" in aia["elements_met"]
    assert aia["detector_versions"].get("stageA")


def test_end_to_end_social_scoring_denies_when_pattern_confirmed():
    labels = _adapter().detect(Event(text=SOCIAL_SCORING))
    pattern_id = next(l for l in labels if l["concept_id"] == "AIA-5-1-c")["pattern_id"]
    data = PolicyData(
        thresholds={"AIA-5-1-c": {"low": 0.45, "high": 0.8, "min_elements": 3}},
        confirmed_prohibited_patterns=[pattern_id],
    )
    assert decide(labels, data) == "deny"
