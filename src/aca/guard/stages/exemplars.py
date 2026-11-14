"""Exemplar loader (R3.3, R3.4).

Loads curated exemplars (positives + hard negatives, DE and EN) per concept and
builds an in-memory embedding index. The index is used by stage 1 for
similarity scoring against the legal-element rubric.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from aca.guard.embeddings import Embedder

_EXEMPLAR_DIR = Path(__file__).resolve().parents[4] / "exemplars"


@dataclass
class Exemplar:
    id: str
    lang: str
    text: str
    elements_met: list[str]
    is_positive: bool
    vector: list[float] = field(default_factory=list)


@dataclass
class ConceptIndex:
    concept_id: str
    pattern_id: str | None
    elements: list[str]
    exemplars: list[Exemplar]

    @property
    def positives(self) -> list[Exemplar]:
        return [e for e in self.exemplars if e.is_positive]

    @property
    def hard_negatives(self) -> list[Exemplar]:
        return [e for e in self.exemplars if not e.is_positive]


def load_concept(concept_id: str, embedder: Embedder, *, exemplar_dir: Path | None = None) -> ConceptIndex:
    base = exemplar_dir or _EXEMPLAR_DIR
    data = json.loads((base / f"{concept_id}.json").read_text(encoding="utf-8"))

    exemplars: list[Exemplar] = []
    for item in data.get("positives", []):
        exemplars.append(
            Exemplar(
                id=item["id"],
                lang=item["lang"],
                text=item["text"],
                elements_met=item.get("elements_met", []),
                is_positive=True,
                vector=embedder.embed(item["text"]),
            )
        )
    for item in data.get("hard_negatives", []):
        exemplars.append(
            Exemplar(
                id=item["id"],
                lang=item["lang"],
                text=item["text"],
                elements_met=item.get("elements_met", []),
                is_positive=False,
                vector=embedder.embed(item["text"]),
            )
        )

    return ConceptIndex(
        concept_id=data["concept_id"],
        pattern_id=data.get("pattern_id"),
        elements=data.get("elements", []),
        exemplars=exemplars,
    )
