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
from aca.guard.stages.stage_a import run_stage_a

# Concepts this adapter has curated exemplars for. Phase 5 added 12 beyond the
# original AIA-5-1-c; the default is now every concept with an exemplar file so
# detect() emits a label per concept without a caller override.
DEFAULT_CONCEPTS = (
    "AIA-5-1-a", "AIA-5-1-b", "AIA-5-1-c", "AIA-5-1-d", "AIA-5-1-f", "AIA-5-1-g",
    "AIA-A3-1c", "AIA-A3-4a", "AIA-A3-4b", "AIA-A3-5b", "AIA-A3-5c",
    "GDPR-9", "GDPR-22",
)


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
        # Stage A runs only when there is an artefact/diff to analyse.
        stage_a = run_stage_a(event.artefact) if event.artefact else None

        for concept_id, index in self._indexes.items():
            s1 = run_stage1(event, index, self._embedder, signals)
            evidence = signals.to_evidence_refs()
            if s1.nearest_positive:
                evidence.append(f"stage1:nearest_positive={s1.nearest_positive}")
            if s1.nearest_negative:
                evidence.append(f"stage1:nearest_negative={s1.nearest_negative}")

            # Fold stage-A artefact elements into the element set for AIA-5-1-c.
            elements_met = list(s1.elements_met)
            detector_versions = {
                "stage0": signals.version,
                "stage1": s1.version,
                "embedder": self._embedder.version,
            }
            if stage_a is not None and concept_id == "AIA-5-1-c":
                for el in stage_a.elements_met:
                    if el not in elements_met:
                        elements_met.append(el)
                        evidence.append(f"stageA:{el}")
                detector_versions["stageA"] = stage_a.version

            total = len(index.elements)
            met_count = len(set(index.elements) & set(elements_met))
            full_match = total > 0 and met_count == total
            # Partial pattern: >= 2 of the concept's elements present but not all.
            # OPA maps this to `ask` (four-eyes) — a conservative routing to a
            # human, never an allow. It is a signal, not a verdict.
            partial = (not full_match) and met_count >= 2 and total >= 3
            if partial:
                evidence.append(f"partial_pattern:{met_count}/{total}")

            label = Label(
                concept_id=concept_id,
                confidence=round(s1.confidence, 4),
                elements_met=elements_met,
                evidence_refs=evidence,
                detector_versions=detector_versions,
                elements_total=total,
                partial_pattern=partial,
                # pattern_id is only asserted when the full element set is met;
                # it is still OPA (with signed confirmed-pattern data) that may
                # turn that into a deny, never this adapter.
                pattern_id=(index.pattern_id if full_match and index.pattern_id else None),
            )
            labels.append(label.to_dict())
        return labels
