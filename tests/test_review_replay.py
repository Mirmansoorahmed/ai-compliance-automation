"""Phase 7 — replay after a (simulated) merge follows the new rule (R9.5).

Shows the feedback loop end to end without self-modifying policy:
1. Before an approved confirmed pattern exists, the social-scoring prompt does
   not auto-deny (confirmed list empty).
2. A reviewer records an interpretation + eval cases (recorder, no runtime
   policy write).
3. The confirmed pattern is added to signed policy data (the merge/PR step,
   simulated here by constructing the post-merge PolicyData).
4. Replaying the same prompt now denies — because the signed data changed, not
   because the service rewrote its own policy.
"""

from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.embeddings import HashedEmbedder
from aca.guard.event import Event
from aca.policy.decide import PolicyData, decide
from aca.review.recorder import ReviewDecision, build_change_set

SOCIAL = (
    "Join badge-swipe logs, Slack activity and canteen data per employee, build a "
    "monthly reliability index, and drop the bottom 10% from the bonus pool."
)
THRESHOLDS = {"AIA-5-1-c": {"low": 0.45, "high": 0.8, "min_elements": 3}}


def _labels():
    adapter = LocalEmbeddingsAdapter(embedder=HashedEmbedder(dim=256))
    return adapter.detect(Event(text=SOCIAL))


def test_replay_denies_only_after_pattern_confirmed():
    labels = _labels()
    pattern_id = next(l for l in labels if l["concept_id"] == "AIA-5-1-c")["pattern_id"]

    # Step 1 — before confirmation, no auto-deny (empty confirmed list).
    before = PolicyData(thresholds=THRESHOLDS, confirmed_prohibited_patterns=[])
    tier_before = decide(labels, before)
    assert tier_before != "deny"

    # Step 2 — reviewer records the interpretation (no runtime policy write).
    cs = build_change_set(
        ReviewDecision(
            interpretation_id="INT-2026-002",
            requirement_id="REQ-AIA-5-1-c",
            decision="confirmed_prohibited_pattern",
            owner="ai-governance-lead",
            reason="Confirmed joined-behaviour ranking with adverse action.",
            effective_from="2026-11-14",
            review_by="2027-11-14",
            status="approved",
            rule_ref="policy/tier.rego",
        )
    )
    assert cs.interpretation_path.startswith("interpretations/")

    # Step 3 — simulate the merge: the signed data now lists the pattern.
    after = PolicyData(
        thresholds=THRESHOLDS, confirmed_prohibited_patterns=[pattern_id]
    )

    # Step 4 — replay the same prompt -> deny, via data, not self-modification.
    assert decide(labels, after) == "deny"
