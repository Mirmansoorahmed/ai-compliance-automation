"""Joint-calibrator bug fixes (ASK optimiser, metrics, fail-loud loader).

These use synthetic caches (no model) for the optimiser, so they are fast and
deterministic. The caches are lists of {concept_id: (confidence, full, partial)}
in the shape _case_cache produces.
"""

import pytest

from aca.eval.calibrate_ask import _review_frac, _solve_joint, _tier_for_case


# --- Fix #1: the optimiser maximises recall, not stops at the first feasible ---

def test_solver_finds_higher_recall_feasible_point():
    # One concept "X". Candidates: top=1.0 (ASK off) and 0.3.
    # 2 benign cases: one has confidence 0.4 (would ASK at 0.3), one 0.0 (never).
    # 4 attack cases with confidence 0.5 (all ASK at 0.3, none at top).
    # At top: recall 0, benign 0. At 0.3: recall 1.0, benign 0.5.
    # Cap 0.6 allows benign 0.5, so the optimiser MUST pick 0.3 (recall 1.0),
    # not stop at the feasible top (recall 0).
    top = 1.0
    cand = [0.3, 1.0]
    benign = [{"X": (0.4, False, False)}, {"X": (0.0, False, False)}]
    attack = [{"X": (0.5, False, False)} for _ in range(4)]
    thr, rec, ben = _solve_joint(benign, attack, ["X"], cand, top, cap=0.6)
    assert thr["X"] == 0.3
    assert rec == 1.0
    assert ben == 0.5


def test_solver_respects_cap_and_prefers_higher_threshold_on_tie():
    # Lowering to 0.3 would push benign review to 0.5 > cap 0.4, so the solver
    # must keep X off (top) -> recall 0.
    top = 1.0
    cand = [0.3, 1.0]
    benign = [{"X": (0.4, False, False)}, {"X": (0.0, False, False)}]
    attack = [{"X": (0.5, False, False)} for _ in range(4)]
    thr, rec, ben = _solve_joint(benign, attack, ["X"], cand, top, cap=0.4)
    assert thr["X"] == top
    assert rec == 0.0 and ben == 0.0


def test_solver_two_concepts_budget_split():
    # Two concepts; cap only allows ASK on the one that buys more recall.
    top = 1.0
    cand = [0.3, 1.0]
    # X: lowering adds 3 attacks, 1 benign. Y: lowering adds 1 attack, 1 benign.
    benign = [{"X": (0.4, False, False), "Y": (0.4, False, False)},
              {"X": (0.0, False, False), "Y": (0.0, False, False)}]
    attack = ([{"X": (0.5, False, False), "Y": (0.0, False, False)}] * 3 +
              [{"X": (0.0, False, False), "Y": (0.5, False, False)}] * 1)
    # Cap 0.5 => at most one benign case may be reviewed. Both concepts lowered
    # would review benign[0] once (either concept triggers it) -> benign 0.5.
    thr, rec, ben = _solve_joint(benign, attack, ["X", "Y"], cand, top, cap=0.5)
    assert ben <= 0.5
    assert rec == 1.0  # both attack groups covered via the single shared benign hit


def test_tier_for_case_full_match_is_four_eyes_regardless_of_threshold():
    facts = {"X": (0.0, True, False)}  # full match, low confidence
    assert _tier_for_case(facts, {"X": 1.0}) == "four-eyes"


def test_review_frac_bounds():
    cache = [{"X": (0.9, False, False)}, {"X": (0.1, False, False)}]
    assert 0.0 <= _review_frac(cache, {"X": 0.5}) <= 1.0


# --- Fix #3: review_recall is a per-attack fraction in [0,1], counts match ---

def test_review_recall_is_per_attack_and_bounded():
    from aca.eval.runner import CaseResult, _prf

    def mk(cat, tier, expect):
        return CaseResult(id=f"{cat}-{tier}-{expect}", lang="en", category=cat,
                          expect_pattern=expect, detected_pattern=(tier in ("deny", "four-eyes")),
                          confidence=0.5, elements_met=[], stage01_latency_ms=0.0,
                          tier=tier, routed_to_review=tier in ("deny", "four-eyes", "ask"))

    results = [
        mk("attack", "ask", True),
        mk("attack", "four-eyes", True),
        mk("attack", "allow", True),        # missed
        mk("benign", "ask", False),         # benign routed — must NOT count in recall
        mk("benign", "allow", False),
    ]
    m = _prf(results)
    assert m["n_attacks"] == 3
    assert m["n_attacks_routed"] == 2            # ask + four-eyes among attacks
    assert m["review_recall"] == round(2 / 3, 4)
    assert 0.0 <= m["review_recall"] <= 1.0
    # Counts match: review_recall * n_attacks is an integer == routed count.
    assert round(m["review_recall"] * m["n_attacks"]) == m["n_attacks_routed"]
    # The benign ASK did not inflate the attack review recall.
    assert m["n"] == 5


def test_review_recall_none_when_no_attacks():
    from aca.eval.runner import CaseResult, _prf
    benign = [CaseResult(id="b", lang="en", category="benign", expect_pattern=False,
                         detected_pattern=False, confidence=0.1, elements_met=[],
                         stage01_latency_ms=0.0, tier="ask", routed_to_review=True)]
    m = _prf(benign)
    assert m["n_attacks"] == 0
    assert m["review_recall"] is None


# --- Fix #4: the shared loader fails loudly when the real model is required ---

def test_resolve_embedder_fails_loudly_when_model_required():
    from aca.guard.embeddings import resolve_embedder
    with pytest.raises(RuntimeError):
        resolve_embedder(require_model=True)


def test_resolve_embedder_env_knob(monkeypatch):
    from aca.guard import embeddings
    monkeypatch.setenv(embeddings.REQUIRE_MODEL_ENV, "1")
    with pytest.raises(RuntimeError):
        embeddings.resolve_embedder()
    monkeypatch.delenv(embeddings.REQUIRE_MODEL_ENV, raising=False)
    # Default: hashed fallback, no raise.
    assert embeddings.resolve_embedder().version.startswith("hashed/")
