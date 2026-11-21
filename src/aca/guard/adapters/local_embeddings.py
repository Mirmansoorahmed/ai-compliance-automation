"""local_embeddings adapter — the required oss Guard backend (R3.1, R3.5, R4.1).

Runs stage 0 (deterministic signals) and stage 1 (embedding similarity vs
curated exemplars) and emits schema-valid labels. Never returns a verdict.

The embedder is the small CPU-only model when installed, else the deterministic
hashed-vector fallback, so this adapter works in CI with no network.
"""

from __future__ import annotations

import json
from pathlib import Path

from aca.guard.embeddings import Embedder, build_embedder
from aca.guard.event import Event
from aca.guard.labels.schema import Label
from aca.guard.stages.elements import ElementIndex, load_element_index, mark_elements
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


_THRESHOLDS_PATH = Path(__file__).resolve().parents[3] / "policy" / "data" / "thresholds.json"


def _load_ask_thresholds() -> dict[str, float]:
    """Per-concept ``ask_threshold`` from the signed thresholds data (Phase A).

    Returns {} if the file or the field is absent, so the similarity tier is
    simply inactive rather than erroring.
    """
    try:
        data = json.loads(_THRESHOLDS_PATH.read_text(encoding="utf-8"))["thresholds"]
    except Exception:
        return {}
    out: dict[str, float] = {}
    for concept_id, th in data.items():
        if isinstance(th, dict) and "ask_threshold" in th:
            out[concept_id] = float(th["ask_threshold"])
    return out


class LocalEmbeddingsAdapter:
    name = "local_embeddings"

    def __init__(
        self,
        *,
        embedder: Embedder | None = None,
        concepts: tuple[str, ...] = DEFAULT_CONCEPTS,
        dim: int = 256,
        ask_thresholds: dict[str, float] | None = None,
        element_margins: dict | None = None,
    ) -> None:
        self._embedder = embedder or build_embedder(allow_hashed_fallback=True, dim=dim)
        self._indexes: dict[str, ConceptIndex] = {
            c: load_concept(c, self._embedder) for c in concepts
        }
        # Per-concept similarity ASK thresholds (Phase A): when the margin is at
        # or above this and the full element match is NOT met, the label carries
        # similarity_only -> OPA routes to ASK (never BLOCK). Loaded from signed
        # thresholds data unless injected (tests/calibration).
        self._ask_thresholds = ask_thresholds if ask_thresholds is not None else _load_ask_thresholds()
        # Phase C: per-element exemplar indexes (embedding-driven element marking
        # for all 13 concepts). ``element_margins`` can be injected (calibration
        # sweeps candidate margins); otherwise the signed element_margins.json is
        # used. A concept with no calibrated entry keeps the prior behaviour and
        # its full match stays disabled until calibrated.
        self._element_indexes: dict[str, ElementIndex] = {}
        for c in concepts:
            ei = load_element_index(c, self._embedder, margins=element_margins)
            if ei is not None:
                self._element_indexes[c] = ei

    def detect(self, event: Event) -> list[dict]:
        signals = run_stage0(event)
        labels: list[dict] = []
        # Stage A runs only when there is an artefact/diff to analyse.
        stage_a = run_stage_a(event.artefact) if event.artefact else None
        query_vec = self._embedder.embed(f"{event.text}\n{event.artefact}".strip())

        for concept_id, index in self._indexes.items():
            s1 = run_stage1(event, index, self._embedder, signals)
            evidence = signals.to_evidence_refs()
            if s1.nearest_positive:
                evidence.append(f"stage1:nearest_positive={s1.nearest_positive}")
            if s1.nearest_negative:
                evidence.append(f"stage1:nearest_negative={s1.nearest_negative}")

            detector_versions = {
                "stage0": signals.version,
                "stage1": s1.version,
                "embedder": self._embedder.version,
            }

            # Phase C: element marking is embedding-driven (per-element exemplars)
            # for every concept whose margins are CALIBRATED. An uncalibrated
            # concept (no entry in element_margins.json — the committed default)
            # does not use element marking at all: it falls back to the prior
            # behaviour (stage-1 keyword elements for AIA-5-1-c, none otherwise),
            # so the offline/hashed default is unchanged and element-driven
            # BLOCK only switches on after the owner calibrates on tuning.
            element_index = self._element_indexes.get(concept_id)
            full_match_disabled = False
            if element_index is not None and element_index.calibrated:
                # Calibrated concept: embedding-driven element marking.
                elements_met = mark_elements(query_vec, element_index)
                for el in elements_met:
                    evidence.append(f"element:{el}")
                full_match_disabled = element_index.full_match_disabled
                # Keep stage-0 keyword hits for AIA-5-1-c as an extra signal.
                if concept_id == "AIA-5-1-c":
                    for el in s1.elements_met:
                        if el not in elements_met:
                            elements_met.append(el)
                            evidence.append(f"stage1kw:{el}")
            else:
                # Uncalibrated concept: prior behaviour only (stage-1 keyword
                # elements for AIA-5-1-c, none for the others). The committed
                # offline default stays here until the owner calibrates.
                elements_met = list(s1.elements_met)
                if element_index is not None:
                    full_match_disabled = element_index.full_match_disabled

            if stage_a is not None and concept_id == "AIA-5-1-c":
                for el in stage_a.elements_met:
                    if el not in elements_met:
                        elements_met.append(el)
                        evidence.append(f"stageA:{el}")
                detector_versions["stageA"] = stage_a.version

            total = len(index.elements)
            met_count = len(set(index.elements) & set(elements_met))
            full_match = total > 0 and met_count == total
            # Phase C: if a concept's element margins are disabled (tuning could
            # not reach a 0 false-block margin), its full match is turned off so
            # it can never BLOCK; it falls back to Phase A's similarity ASK.
            if full_match_disabled:
                full_match = False
                evidence.append("full_match_disabled")
            # Partial pattern: >= 2 of the concept's elements present but not all.
            # OPA maps this to `ask` (four-eyes) — a conservative routing to a
            # human, never an allow. It is a signal, not a verdict.
            partial = (not full_match) and met_count >= 2 and total >= 3
            if partial:
                evidence.append(f"partial_pattern:{met_count}/{total}")

            # Phase A: a confident similarity match WITHOUT a full element match
            # is a similarity_only signal -> ASK. Never set when the full match
            # is present (that path is already four-eyes), so it only ever adds
            # review, never a BLOCK.
            ask_th = self._ask_thresholds.get(concept_id)
            similarity_only = bool(
                ask_th is not None and not full_match and s1.confidence >= ask_th
            )
            if similarity_only:
                evidence.append(f"similarity_only:{round(s1.confidence, 4)}>={ask_th}")

            label = Label(
                concept_id=concept_id,
                confidence=round(s1.confidence, 4),
                elements_met=elements_met,
                evidence_refs=evidence,
                detector_versions=detector_versions,
                elements_total=total,
                partial_pattern=partial,
                similarity_only=similarity_only,
                # pattern_id is only asserted when the full element set is met;
                # it is still OPA (with signed confirmed-pattern data) that may
                # turn that into a deny, never this adapter.
                pattern_id=(index.pattern_id if full_match and index.pattern_id else None),
            )
            labels.append(label.to_dict())
        return labels
