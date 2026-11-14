"""local_embeddings adapter — the required oss Guard backend (R3.1, R3.5, R4.1).

Runs stage 0 (deterministic signals) and stage 1 (embedding similarity vs
curated exemplars) and emits schema-valid labels. Never returns a verdict.

The embedder is the small CPU-only model when installed, else the deterministic
hashed-vector fallback, so this adapter works in CI with no network.
"""

from __future__ import annotations

from aca.guard.embeddings import Embedder, build_embedder
from aca.guard.event import Event
from aca.guard.labels.schema import Label
from aca.guard.stages.exemplars import ConceptIndex, load_concept
from aca.guard.stages.stage0 import run_stage0
from aca.guard.stages.stage1 import run_stage1

# Concepts this adapter has curated exemplars for in v1.
DEFAULT_CONCEPTS = ("AIA-5-1-c",)


class LocalEmbeddingsAdapter:
    name = "local_embeddings"

    def __init__(
        self,
        *,
        embedder: Embedder | None = None,
        concepts: tuple[str, ...] = DEFAULT_CONCEPTS,
        dim: int = 256,
    ) -> None:
        self._embedder = embedder or build_embedder(allow_hashed_fallback=True, dim=dim)
        self._indexes: dict[str, ConceptIndex] = {
            c: load_concept(c, self._embedder) for c in concepts
        }

    def detect(self, event: Event) -> list[dict]:
        signals = run_stage0(event)
        labels: list[dict] = []
        for concept_id, index in self._indexes.items():
            s1 = run_stage1(event, index, self._embedder, signals)
            evidence = signals.to_evidence_refs()
            if s1.nearest_positive:
                evidence.append(f"stage1:nearest_positive={s1.nearest_positive}")
            if s1.nearest_negative:
                evidence.append(f"stage1:nearest_negative={s1.nearest_negative}")

            label = Label(
                concept_id=concept_id,
                confidence=round(s1.confidence, 4),
                elements_met=s1.elements_met,
                evidence_refs=evidence,
                detector_versions={
                    "stage0": signals.version,
                    "stage1": s1.version,
                    "embedder": self._embedder.version,
                },
                # pattern_id is only asserted when the full element set is met;
                # it is still OPA (with signed confirmed-pattern data) that may
                # turn that into a deny, never this adapter.
                pattern_id=(
                    index.pattern_id
                    if index.pattern_id and set(index.elements) <= set(s1.elements_met)
                    else None
                ),
            )
            labels.append(label.to_dict())
        return labels
