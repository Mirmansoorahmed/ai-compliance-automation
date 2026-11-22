"""Phase 5 — wider detection: exemplar data integrity + offline smoke eval.

These assert the new exemplar files are well-formed and loadable, that each
concept id matches the catalog, and that the per-concept smoke eval runs
offline. The smoke accuracy is a DATA sanity signal (hashed embedder), NOT a
model metric — real recall is measured by the owner with MiniLM.
"""

import json
from pathlib import Path

import pytest

from aca.catalog.loader import load_catalog
from aca.eval.concepts import run_smoke
from aca.guard.embeddings import build_embedder
from aca.guard.stages.exemplars import load_concept

_ROOT = Path(__file__).resolve().parents[1]
_EXEMPLAR_DIR = _ROOT / "exemplars"
_HELDOUT_V2 = _ROOT / "eval" / "heldout_v2"

# Concepts added in Phase 5 (plus the pre-existing AIA-5-1-c).
_NEW_CONCEPTS = [
    "AIA-5-1-a", "AIA-5-1-b", "AIA-5-1-d", "AIA-5-1-f", "AIA-5-1-g",
    "AIA-A3-4a", "AIA-A3-4b", "AIA-A3-5b", "AIA-A3-5c", "AIA-A3-1c",
    "GDPR-9", "GDPR-22",
]


def _catalog_ids():
    return {c["id"] for c in load_catalog()["checks"]}


def test_all_new_exemplar_files_present():
    for cid in _NEW_CONCEPTS:
        assert (_EXEMPLAR_DIR / f"{cid}.json").is_file(), f"missing exemplars for {cid}"


@pytest.mark.parametrize("cid", _NEW_CONCEPTS)
def test_exemplar_file_well_formed(cid):
    data = json.loads((_EXEMPLAR_DIR / f"{cid}.json").read_text(encoding="utf-8"))
    assert data["concept_id"] == cid
    assert data.get("elements"), f"{cid} has no legal elements"
    assert data.get("positives"), f"{cid} has no positives"
    assert data.get("hard_negatives"), f"{cid} has no hard negatives"
    # Positives must meet every element; negatives meet none.
    required = set(data["elements"])
    for p in data["positives"]:
        assert set(p["elements_met"]) == required, f"{cid} positive {p['id']} must meet all elements"
    for n in data["hard_negatives"]:
        assert n["elements_met"] == [], f"{cid} negative {n['id']} must meet no elements"
    # DE and EN are both represented.
    langs = {x["lang"] for x in data["positives"]}
    assert {"de", "en"} <= langs, f"{cid} positives must cover de and en"


def test_concept_ids_match_catalog():
    ids = _catalog_ids()
    for cid in _NEW_CONCEPTS:
        assert cid in ids, f"{cid} not in catalog.yaml"


@pytest.mark.parametrize("cid", _NEW_CONCEPTS)
def test_exemplars_load_through_guard_loader(cid):
    embedder = build_embedder(allow_hashed_fallback=True, dim=256)
    idx = load_concept(cid, embedder, exemplar_dir=_EXEMPLAR_DIR)
    assert idx.concept_id == cid
    assert idx.positives and idx.hard_negatives
    assert all(e.vector for e in idx.exemplars)  # embedded


def test_smoke_eval_runs_and_is_labelled_by_active_embedder():
    # The label depends on the embedder actually loaded: the hashed fallback
    # says "smoke"; the trained sentence-transformers model says it is a model
    # separation signal. Accept whichever matches the active embedder.
    from aca.eval.concepts import _HASHED_LABEL, _MODEL_LABEL
    report = run_smoke()
    if report["is_smoke"]:
        assert report["label"] == _HASHED_LABEL
        assert "smoke" in report["label"].lower()
    else:
        assert report["label"] == _MODEL_LABEL
        assert "smoke" not in report["label"].lower()
    assert report["n_concepts"] >= len(_NEW_CONCEPTS)
    for c in report["concepts"]:
        assert c["loo_accuracy"] is None or 0.0 <= c["loo_accuracy"] <= 1.0


def test_smoke_eval_hashed_label_when_forced_hashed():
    # Forcing the hashed embedder must always produce the smoke label.
    from aca.eval.concepts import _HASHED_LABEL, smoke_concept
    from aca.guard.embeddings import HashedEmbedder
    emb = HashedEmbedder(dim=256)
    assert not str(emb.version).startswith("st:")
    r = smoke_concept(_EXEMPLAR_DIR / "AIA-5-1-c.json", emb)
    assert r.loo_accuracy is None or 0.0 <= r.loo_accuracy <= 1.0
    # _label_for picks the hashed label for a non-"st:" embedder.
    from aca.eval.concepts import _label_for
    assert _label_for(emb) == _HASHED_LABEL


def test_heldout_v2_cases_load_and_reference_known_concepts():
    from aca.register.yamlio import load_yaml
    ids = _catalog_ids()
    files = sorted(_HELDOUT_V2.glob("*.yaml"))
    assert files, "no held-out v2 cases"
    for p in files:
        case = load_yaml(p)
        assert case["concept_id"] in ids
        assert isinstance(case["expect_pattern"], bool)
        assert case["category"] in ("attack", "benign", "ambiguous")
