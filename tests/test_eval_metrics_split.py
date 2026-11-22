"""Fix #3 — benign outcome split (ASK / four-eyes / BLOCK) and review recall."""

from aca.eval.runner import CaseResult, _benign_rates, _prf


def _case(cat, tier, *, expect=False, detected=False):
    return CaseResult(
        id=f"{cat}-{tier}", lang="en", category=cat, expect_pattern=expect,
        detected_pattern=detected, confidence=0.5, elements_met=[],
        stage01_latency_ms=0.0, tier=tier,
        routed_to_review=tier in ("deny", "four-eyes", "ask"),
    )


def test_benign_rates_split_by_tier():
    benign = [
        _case("benign", "allow"),
        _case("benign", "ask"),
        _case("benign", "ask"),
        _case("benign", "four-eyes", detected=True),
        _case("benign", "deny", detected=True),
    ]
    r = _benign_rates(benign)
    assert r["n_benign"] == 5
    assert r["benign_ask_rate"] == 0.4            # 2/5
    assert r["benign_four_eyes_rate"] == 0.2      # 1/5
    assert r["benign_block_rate"] == 0.2          # 1/5
    # false-block = block + four-eyes (both are a hard blocking review).
    assert r["benign_false_block_rate"] == 0.4    # 2/5
    # review = block + four-eyes + ask.
    assert r["benign_review_rate"] == 0.8         # 4/5


def test_benign_rates_empty():
    r = _benign_rates([_case("attack", "deny", expect=True, detected=True)])
    assert r["n_benign"] == 0
    assert r["benign_review_rate"] is None


def test_review_recall_counts_block_foureyes_and_ask():
    attacks = [
        _case("attack", "deny", expect=True, detected=True),
        _case("attack", "four-eyes", expect=True, detected=True),
        _case("attack", "ask", expect=True),
        _case("attack", "allow", expect=True),   # missed
    ]
    m = _prf(attacks)
    # routed_to_review (review recall) = 3 of 4 attacks reached a human.
    assert m["routed_to_review"] == 0.75
    # strict recall = full matches only (deny + four-eyes detected) = 2 of 4.
    assert m["recall"] == 0.5
