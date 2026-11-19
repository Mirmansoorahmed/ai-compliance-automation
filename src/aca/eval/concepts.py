"""Per-concept exemplar smoke eval (Phase 5).

Phase 5 ships exemplars + legal elements for many concepts (the remaining Art. 5
points and the fintech-relevant Annex III areas and GDPR Art. 9/22). This module
computes a per-concept leave-one-out nearest-exemplar separation score and
writes a result JSON to eval/results/.

It is a DATA-QUALITY signal, not a held-out recall number. The label and the
``is_smoke`` flag depend on the embedder actually loaded: with the OFFLINE
hashed fallback it is a smoke check (the data loads and positives/negatives are
not trivially inseparable), explicitly labelled "smoke, not a real result"; with
the trained sentence-transformers model it is labelled a model separation signal
(still a data-quality check, not recall). The real recall numbers come from the
eval runner's held-out scoring with the trained model, run by the owner.

For each concept it embeds every exemplar, and for each one checks whether its
nearest OTHER exemplar has the same polarity (positive vs hard negative). The
reported ``loo_accuracy`` is that agreement rate.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from aca.guard.embeddings import build_embedder, cosine

_EXEMPLAR_DIR = Path(__file__).resolve().parents[3] / "exemplars"
_RESULTS_DIR = Path(__file__).resolve().parents[3] / "eval" / "results"

# Label text depends on the embedder actually loaded (set at run time).
_HASHED_LABEL = ("smoke, not a real result (offline hashed embedder; real recall "
                 "is measured by the owner with MiniLM)")
_MODEL_LABEL = ("per-concept leave-one-out separation on the trained model "
                "(a data-quality signal, not a held-out recall number)")

# Back-compat alias (tests referenced SMOKE_LABEL).
SMOKE_LABEL = _HASHED_LABEL


def _is_hashed(embedder) -> bool:
    return not str(getattr(embedder, "version", "")).startswith("st:")


def _label_for(embedder) -> str:
    return _HASHED_LABEL if _is_hashed(embedder) else _MODEL_LABEL


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
        "schema": "concept-separation/v1",
        "generated_ts": time.time(),
        "embedder": embedder.version,
        "embedder_backend": "hashed-fallback" if _is_hashed(embedder) else "sentence-transformers",
        "is_smoke": _is_hashed(embedder),
        "label": _label_for(embedder),
        "n_concepts": len(results),
        "concepts": [r.__dict__ for r in results],
    }


def write_report(report: dict, *, results_dir: Path | None = None) -> Path:
    base = results_dir or _RESULTS_DIR
    base.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(report.get("generated_ts", 0)))
    backend = "hashed" if report.get("is_smoke") else "model"
    path = base / f"concept-separation-{stamp}-{backend}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return path


def main() -> int:  # pragma: no cover - CLI glue
    report = run_smoke()
    path = write_report(report)
    print("Per-concept exemplar separation check")
    print(f"  {report['label']}")
    print(f"  embedder: {report['embedder']}  concepts: {report['n_concepts']}")
    print(f"  result written: {path}\n")
    tag = "smoke" if report["is_smoke"] else "model"
    for c in report["concepts"]:
        print(f"  {c['concept_id']:14} pos={c['n_positives']} neg={c['n_negatives']} "
              f"loo_accuracy({tag})={c['loo_accuracy']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
