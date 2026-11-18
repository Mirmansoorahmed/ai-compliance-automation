"""Stage 1 — embedding similarity vs curated exemplars (R3.3, R3.5).

Scores an event against a concept's exemplars (positives and hard negatives)
using cosine similarity in the embedding space. The similarity to positives,
tempered by similarity to hard negatives, gives a confidence. Stage-0 element
hints refine which legal elements are marked met.

This is rubric + exemplar based, not a keyword decision: keywords feed stage 0
as *signals*, but the confidence comes from similarity to curated examples, so
"fraud risk score" (a hard negative) stays low even though it contains "score".
"""

from __future__ import annotations

from dataclasses import dataclass

from aca.guard.embeddings import Embedder, cosine
from aca.guard.event import Event
from aca.guard.stages.exemplars import ConceptIndex
from aca.guard.stages.stage0 import Stage0Signals

STAGE1_VERSION = "stage1/0.1.0"


@dataclass(frozen=True)
class Stage1Result:
    concept_id: str
    pattern_id: str | None
    confidence: float
    elements_met: list[str]
    nearest_positive: str | None
    nearest_negative: str | None
    version: str = STAGE1_VERSION


def _max_sim(vec: list[float], index_items) -> tuple[float, str | None]:
    best = 0.0
    best_id = None
    for ex in index_items:
        sim = cosine(vec, ex.vector)
        if sim > best:
            best = sim
            best_id = ex.id
    return best, best_id


def run_stage1(
    event: Event,
    index: ConceptIndex,
    embedder: Embedder,
    signals: Stage0Signals,
) -> Stage1Result:
    query = f"{event.text}\n{event.artefact}".strip()
    qvec = embedder.embed(query)

    pos_sim, nearest_pos = _max_sim(qvec, index.positives)
    neg_sim, nearest_neg = _max_sim(qvec, index.hard_negatives)

    # Confidence is the margin of the nearest positive over the nearest hard
    # negative: relu(pos_sim - neg_sim), clamped to [0, 1]. A request close to a
    # hard negative (e.g. "fraud risk score") therefore scores low even when it
    # is somewhat similar to a positive. Explainable and monotone.
    margin = pos_sim - neg_sim
    confidence = max(0.0, min(1.0, margin))

    # Mark elements using stage-0 structural hints. For AIA-5-1-c the three
    # elements map to behaviour-join, aggregated score, and adverse action.
    elements_met: list[str] = []
    if index.concept_id == "AIA-5-1-c":
        if signals.behaviour_hits >= 2 or (signals.has_pii and signals.behaviour_hits >= 1):
            elements_met.append("person_identifiable_behaviour_join")
        if signals.score_hits >= 1:
            elements_met.append("aggregated_score_or_ranking")
        if signals.adverse_hits >= 1:
            elements_met.append("adverse_action")

    return Stage1Result(
        concept_id=index.concept_id,
        pattern_id=index.pattern_id,
        confidence=confidence,
        elements_met=elements_met,
        nearest_positive=nearest_pos,
        nearest_negative=nearest_neg,
    )
