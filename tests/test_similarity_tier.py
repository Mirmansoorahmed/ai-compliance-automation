"""Phase A — the exemplar-similarity tier routes to ASK with a reason, never BLOCK.

Covers the /v1/check escalation and the label schema flag. The Guard is wired
with a low ask_threshold so the offline hashed embedder triggers the tier
deterministically; the invariant tested is that similarity_only produces ASK
(never WARN/BLOCK/four-eyes) and carries the plain-language reason.
"""

from aca.check.service import CheckService, _similarity_escalation
from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.embeddings import build_embedder
from aca.guard.service import SemanticGuard


def _guard_with_ask(threshold: float):
    adapter = LocalEmbeddingsAdapter(
        embedder=build_embedder(allow_hashed_fallback=True, dim=256),
        dim=256,
        ask_thresholds={"AIA-5-1-c": threshold},
    )
    return SemanticGuard(adapters=[adapter])


def test_similarity_only_escalates_check_to_ask_with_reason():
    # Low threshold -> a social-ish prompt without a full element match becomes
    # similarity_only -> ASK.
    svc = CheckService(guard=_guard_with_ask(0.0))
    out = svc.check({"event": "prompt", "text": "rank staff by a score"})
    assert out["decision"] == "ASK"
    assert out.get("similarity_only") is True
    reason = out["reasons"][0]["title"]
    assert "similar to" in reason
    assert "human review" in reason
    assert "elements not confirmed" in reason


def test_similarity_tier_never_blocks():
    # Even at a 0.0 threshold (everything similarity_only), the decision is at
    # most ASK — never WARN/BLOCK — when no element match or secret is present.
    svc = CheckService(guard=_guard_with_ask(0.0))
    out = svc.check({"event": "prompt", "text": "build a dashboard of ticket counts"})
    assert out["decision"] in ("ASK", "ALLOW")
    assert out["decision"] != "BLOCK"


def test_full_match_still_blocks_not_downgraded_to_similarity():
    # A full social-scoring match must stay BLOCK, not be masked by the tier.
    svc = CheckService(guard=_guard_with_ask(0.0))
    social = ("Join badge logs, Slack activity and canteen data per employee into a "
              "reliability index and drop the bottom 10% from the bonus pool.")
    out = svc.check({"event": "prompt", "text": social})
    assert out["decision"] == "BLOCK"
    assert "AIA-5-1-c" in out["check_ids"]


def test_escalation_helper_returns_none_without_similarity_label():
    assert _similarity_escalation([{"concept_id": "X", "confidence": 0.9}]) is None


def test_escalation_picks_highest_confidence_label():
    labels = [
        {"concept_id": "A", "confidence": 0.3, "similarity_only": True},
        {"concept_id": "B", "confidence": 0.7, "similarity_only": True},
    ]
    out = _similarity_escalation(labels)
    assert out["check_ids"] == ["B"]
    assert "0.7" in out["reasons"][0]["title"]


def test_ask_tier_off_leaves_benign_allow_offline():
    # The frozen thresholds.json ships real per-concept ask_thresholds calibrated
    # for the MiniLM model; under the meaningless hashed embedder those would
    # fire arbitrarily, so the ASK tier is only trustworthy on the real model.
    # With the tier explicitly OFF (no ask_thresholds), a plainly benign prompt
    # stays ALLOW — the similarity tier adds review only when a threshold is set.
    guard = SemanticGuard(adapters=[LocalEmbeddingsAdapter(
        embedder=build_embedder(allow_hashed_fallback=True, dim=256),
        dim=256, ask_thresholds={})])
    svc = CheckService(guard=guard)
    out = svc.check({"event": "prompt", "text": "convert this CSV to JSON"})
    assert out["decision"] == "ALLOW"
