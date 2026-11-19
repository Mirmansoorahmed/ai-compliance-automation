"""Per-concept exemplar smoke eval (Phase 5).

Phase 5 ships exemplars + legal elements for many concepts (the remaining Art. 5
points and the fintech-relevant Annex III areas and GDPR Art. 9/22). The real
recall numbers must come from a run with the trained MiniLM model, done by the
owner on another machine. This module is a **smoke check only**: a leave-one-out
nearest-exemplar separation score computed with the OFFLINE hashed embedder, so
CI can confirm the data loads and the positives/negatives are not trivially
inseparable. Its output is explicitly labelled "smoke, not a real result".

For each concept it embeds every exemplar, and for each held-out exemplar checks
whether its nearest OTHER exemplar has the same polarity (positive vs hard
negative). The reported ``loo_accuracy`` is that agreement rate. This is a data
sanity signal, not a model metric.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from aca.guard.embeddings import build_embedder, cosine

_EXEMPLAR_DIR = Path(__file__).resolve().parents[3] / "exemplars"

SMOKE_LABEL = "smoke, not a real result (offline hashed embedder; real recall is measured by the owner with MiniLM)"


@dataclass
class ConceptSmoke:
    concept_id: str
    n_positives: int
    n_negatives: int
    loo_accuracy: float | None
    elements: list[str] = field(default_factory=list)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _items(data: dict) -> list[tuple[str, bool]]:
    items: list[tuple[str, bool]] = []
    for p in data.get("positives", []):
        items.append((p["text"], True))
    for n in data.get("hard_negatives", []):
        items.append((n["text"], False))
    return items


def smoke_concept(path: Path, embedder) -> ConceptSmoke:
    data = _load(path)
    items = _items(data)
    vectors = [(embedder.embed(text), pol) for text, pol in items]
    pos = sum(1 for _, pol in items if pol)
    neg = len(items) - pos

    correct = 0
    scored = 0
    for i, (vi, poli) in enumerate(vectors):
        best_j, best_sim = -1, -2.0
        for j, (vj, _polj) in enumerate(vectors):
            if i == j:
                continue
            sim = cosine(vi, vj)
            if sim > best_sim:
                best_sim, best_j = sim, j
        if best_j >= 0:
            scored += 1
            if vectors[best_j][1] == poli:
                correct += 1
    acc = round(correct / scored, 4) if scored else None

    return ConceptSmoke(
        concept_id=data["concept_id"],
        n_positives=pos,
        n_negatives=neg,
        loo_accuracy=acc,
        elements=data.get("elements", []),
    )


def run_smoke(*, exemplar_dir: Path | None = None) -> dict:
    base = exemplar_dir or _EXEMPLAR_DIR
    embedder = build_embedder(allow_hashed_fallback=True, dim=256)
    results = []
    for path in sorted(base.glob("*.json")):
        results.append(smoke_concept(path, embedder))
    return {
        "label": SMOKE_LABEL,
        "embedder": embedder.version,
        "n_concepts": len(results),
        "concepts": [r.__dict__ for r in results],
    }


def main() -> int:  # pragma: no cover - CLI glue
    report = run_smoke()
    print("Per-concept exemplar smoke check")
    print(f"  {report['label']}")
    print(f"  embedder: {report['embedder']}  concepts: {report['n_concepts']}\n")
    for c in report["concepts"]:
        print(f"  {c['concept_id']:14} pos={c['n_positives']} neg={c['n_negatives']} "
              f"loo_accuracy(smoke)={c['loo_accuracy']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
