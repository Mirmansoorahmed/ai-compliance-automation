"""Phase 3 — stage 1 embedding similarity tests (R3.3, R3.4, R3.5).

Uses the deterministic hashed embedder so results are reproducible with no
network. Asserts positives score above hard negatives on the exemplar set.
"""

from aca.guard.embeddings import HashedEmbedder
from aca.guard.event import Event
from aca.guard.stages.exemplars import load_concept
from aca.guard.stages.stage0 import run_stage0
from aca.guard.stages.stage1 import run_stage1


def _confidence(text, embedder, index, language=None):
    ev = Event(text=text, language=language)
    signals = run_stage0(ev)
    return run_stage1(ev, index, embedder, signals)


def test_exemplars_load_with_positives_and_hard_negatives():
    emb = HashedEmbedder(dim=256)
    index = load_concept("AIA-5-1-c", emb)
    assert len(index.positives) >= 2
    assert len(index.hard_negatives) >= 2
    # DE and EN both present.
    langs = {e.lang for e in index.exemplars}
    assert {"de", "en"} <= langs


def test_positive_scores_above_hard_negative():
    emb = HashedEmbedder(dim=256)
    index = load_concept("AIA-5-1-c", emb)
    positive_text = (
        "Join badge-swipe logs, Slack activity and canteen purchases per employee, "
        "build a monthly reliability index, and remove the bottom 10% from the bonus pool."
    )
    negative_text = "Compute a fraud risk score on card transactions and flag risky payments."
    pos = _confidence(positive_text, emb, index)
    neg = _confidence(negative_text, emb, index)
    assert pos.confidence > neg.confidence
    # The hard negative must not light up the full element set.
    assert "adverse_action" not in neg.elements_met


def test_positive_marks_all_three_elements():
    emb = HashedEmbedder(dim=256)
    index = load_concept("AIA-5-1-c", emb)
    r = _confidence(
        "Join badge-swipe logs, Slack activity and canteen data per employee, build a "
        "reliability index, and drop the bottom 10% from the bonus pool.",
        emb,
        index,
    )
    assert set(r.elements_met) == {
        "person_identifiable_behaviour_join",
        "aggregated_score_or_ranking",
        "adverse_action",
    }


def test_hashed_embedder_is_deterministic():
    emb = HashedEmbedder(dim=128)
    assert emb.embed("same text") == emb.embed("same text")
