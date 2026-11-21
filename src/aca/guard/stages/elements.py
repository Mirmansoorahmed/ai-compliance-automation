"""Element-level exemplar marking (Phase C).

Phase A added an ASK tier for confident-but-unconfirmed similarity. Phase C makes
the *element* step itself embedding-driven for all 13 concepts, instead of the
old keyword block that only handled AIA-5-1-c.

Each legal element of each concept has its own positive and negative exemplars
(exemplars/elements/<concept>.json). An element is marked MET when the query's
max cosine similarity to that element's positives exceeds its max similarity to
that element's negatives by at least a per-element margin (calibrated on the
tuning set, policy/data/element_margins.json). A full element match is what the
decision layer turns into BLOCK/four-eyes — so Phase C can lift strict recall,
and its margins are set so the tuning false-block rate is 0 (a concept that
cannot reach that has its full match disabled and falls back to Phase A's ASK).

Dependency-free; uses the same embedder as the rest of stage 1.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from aca.guard.embeddings import Embedder, cosine

_ELEMENTS_DIR = Path(__file__).resolve().parents[4] / "exemplars" / "elements"
_MARGINS_PATH = Path(__file__).resolve().parents[4] / "policy" / "data" / "element_margins.json"

DEFAULT_MARGIN = 0.05


@dataclass
class _ElementExemplars:
    positives: list[list[float]] = field(default_factory=list)
    negatives: list[list[float]] = field(default_factory=list)


@dataclass
class ElementIndex:
    concept_id: str
    # element name -> embedded positive/negative exemplar vectors.
    elements: dict[str, _ElementExemplars]
    margins: dict[str, float]
    # Concepts whose full match is disabled because tuning could not reach a
    # 0 false-block margin (set in the margins file as margin == null), or
    # because the concept is not calibrated yet.
    full_match_disabled: bool = False
    # True when this concept has a calibrated margins entry. Element marking is
    # used for marking only when calibrated; otherwise the adapter keeps the
    # prior (keyword) behaviour so the uncalibrated default is unchanged.
    calibrated: bool = False


def load_margins(path: Path | None = None) -> dict:
    p = path or _MARGINS_PATH
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_element_index(concept_id: str, embedder: Embedder, *,
                       elements_dir: Path | None = None,
                       margins: dict | None = None) -> ElementIndex | None:
    base = elements_dir or _ELEMENTS_DIR
    path = base / f"{concept_id}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    margins_data = margins if margins is not None else load_margins()
    all_concept_margins = margins_data.get("concepts", {}) if isinstance(margins_data, dict) else {}
    concept_margins = all_concept_margins.get(concept_id, {}) if isinstance(all_concept_margins, dict) else {}

    # A concept with NO calibrated margins entry is NOT calibrated for
    # element-driven full matches: its full match via element marking is
    # DISABLED so it can never BLOCK on an uncalibrated margin. AIA-5-1-c is
    # exempt because it has an independent, established keyword full-match path
    # (pre-Phase-C) that must keep working with or without element calibration.
    # The owner's real-model calibration populates ``concepts`` to enable the
    # other 12. Keeps the committed hashed default safe: no NEW element-driven
    # BLOCK until calibrated.
    calibrated = bool(concept_margins)
    disabled = (not calibrated) and concept_id != "AIA-5-1-c"

    elements: dict[str, _ElementExemplars] = {}
    el_margins: dict[str, float] = {}
    for element, sets in data.get("elements", {}).items():
        ex = _ElementExemplars(
            positives=[embedder.embed(t) for t in sets.get("positives", [])],
            negatives=[embedder.embed(t) for t in sets.get("negatives", [])],
        )
        elements[element] = ex
        m = concept_margins.get(element, {}) if isinstance(concept_margins, dict) else {}
        margin = m.get("margin", DEFAULT_MARGIN) if isinstance(m, dict) else m
        if margin is None:
            disabled = True  # an element with a null margin disables full match
            el_margins[element] = float("inf")
        else:
            el_margins[element] = float(margin)

    return ElementIndex(concept_id=concept_id, elements=elements,
                        margins=el_margins, full_match_disabled=disabled,
                        calibrated=calibrated)


def _max_sim(qvec: list[float], vecs: list[list[float]]) -> float:
    best = 0.0
    for v in vecs:
        s = cosine(qvec, v)
        if s > best:
            best = s
    return best


def mark_elements(qvec: list[float], index: ElementIndex) -> list[str]:
    """Return the element names marked MET for the query vector."""
    met: list[str] = []
    for element, ex in index.elements.items():
        pos = _max_sim(qvec, ex.positives)
        neg = _max_sim(qvec, ex.negatives)
        margin = index.margins.get(element, DEFAULT_MARGIN)
        if (pos - neg) >= margin:
            met.append(element)
    return met


@lru_cache(maxsize=None)
def available_element_concepts(elements_dir: Path | None = None) -> tuple[str, ...]:
    base = elements_dir or _ELEMENTS_DIR
    if not base.exists():
        return ()
    return tuple(sorted(p.stem for p in base.glob("*.json")))
