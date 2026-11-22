"""Phase C — element-level exemplars: data integrity, disjointness, marking.

Uses the offline hashed embedder. Checks the per-element exemplar files are
well-formed and disjoint from the concept exemplars, tuning, and held-out sets;
that element marking works when a concept is calibrated (injected margins); and
that an uncalibrated concept keeps the prior behaviour (full match off for the
new concepts, keyword path for AIA-5-1-c).
"""

import json
import re
from pathlib import Path

import pytest

from aca.guard.embeddings import build_embedder
from aca.guard.stages.elements import (
    DEFAULT_MARGIN,
    load_element_index,
    mark_elements,
)
from aca.register.yamlio import load_yaml

_ROOT = Path(__file__).resolve().parents[1]
_ELEMENTS = _ROOT / "exemplars" / "elements"
_CONCEPT_EXEMPLARS = _ROOT / "exemplars"
_TUNING = (_ROOT / "eval" / "cases", _ROOT / "eval" / "tuning_v2")
_HELDOUT = (_ROOT / "eval" / "heldout", _ROOT / "eval" / "heldout_v2")

_ALL_CONCEPTS = {
    "AIA-5-1-a", "AIA-5-1-b", "AIA-5-1-c", "AIA-5-1-d", "AIA-5-1-f", "AIA-5-1-g",
    "AIA-A3-1c", "AIA-A3-4a", "AIA-A3-4b", "AIA-A3-5b", "AIA-A3-5c",
    "GDPR-9", "GDPR-22",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _element_texts() -> set[str]:
    texts = set()
    for p in _ELEMENTS.glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        for _el, sets in d["elements"].items():
            for t in sets["positives"] + sets["negatives"]:
                texts.add(_norm(t))
    return texts


def test_every_concept_has_an_element_file_with_all_elements():
    for cid in _ALL_CONCEPTS:
        p = _ELEMENTS / f"{cid}.json"
        assert p.is_file(), f"missing element file for {cid}"
        d = json.loads(p.read_text(encoding="utf-8"))
        # Element names must match the concept's declared elements.
        concept = json.loads((_CONCEPT_EXEMPLARS / f"{cid}.json").read_text(encoding="utf-8"))
        assert set(d["elements"]) == set(concept["elements"]), cid


def test_each_element_has_six_pos_six_neg_de_en():
    for p in _ELEMENTS.glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        for el, sets in d["elements"].items():
            assert len(sets["positives"]) >= 6, f"{p.name}:{el} positives"
            assert len(sets["negatives"]) >= 6, f"{p.name}:{el} negatives"


def test_element_texts_disjoint_from_concept_exemplars_tuning_heldout():
    forbidden = set()
    # concept exemplars
    for p in _CONCEPT_EXEMPLARS.glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        for group in ("positives", "hard_negatives"):
            for item in d.get(group, []):
                forbidden.add(_norm(item.get("text", "")))
    # tuning + held-out
    for dirs in (_TUNING, _HELDOUT):
        for d in dirs:
            for p in d.glob("*.yaml"):
                c = load_yaml(p)
                if c.get("text"):
                    forbidden.add(_norm(c["text"]))
    clashes = sorted(_element_texts() & forbidden)
    assert not clashes, f"element exemplar text reused elsewhere: {clashes[:5]}"


def test_no_duplicate_element_texts():
    from collections import Counter
    counts = Counter()
    for p in _ELEMENTS.glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        for _el, sets in d["elements"].items():
            for t in sets["positives"] + sets["negatives"]:
                counts[_norm(t)] += 1
    dups = [t for t, n in counts.items() if n > 1]
    assert not dups, f"duplicate element exemplar texts: {len(dups)}"


def test_calibrated_concept_marks_its_positive_element():
    # Inject a calibrated margins dict so marking is active, then a text close
    # to an element's positive marks that element.
    emb = build_embedder(allow_hashed_fallback=True, dim=256)
    margins = {"concepts": {"AIA-A3-5b": {
        "assesses_natural_person_creditworthiness": {"margin": 0.0},
        "affects_access_to_credit": {"margin": 0.0},
    }}}
    idx = load_element_index("AIA-A3-5b", emb, margins=margins)
    assert idx is not None and idx.calibrated is True
    # A creditworthiness sentence should mark at least one element at margin 0.
    marks = mark_elements(emb.embed("judge a person's creditworthiness to set their loan limit"), idx)
    assert marks  # at least one element marked


def test_uncalibrated_new_concept_has_full_match_disabled():
    emb = build_embedder(allow_hashed_fallback=True, dim=256)
    idx = load_element_index("AIA-A3-5b", emb, margins={"concepts": {}})
    assert idx is not None
    assert idx.calibrated is False
    assert idx.full_match_disabled is True


def test_uncalibrated_aia_5_1_c_is_not_disabled():
    # AIA-5-1-c keeps its keyword full-match path even when element margins are
    # not calibrated, so it is never disabled by the uncalibrated rule.
    emb = build_embedder(allow_hashed_fallback=True, dim=256)
    idx = load_element_index("AIA-5-1-c", emb, margins={"concepts": {}})
    assert idx is not None
    assert idx.calibrated is False
    assert idx.full_match_disabled is False


def test_null_margin_disables_full_match():
    emb = build_embedder(allow_hashed_fallback=True, dim=256)
    margins = {"concepts": {"GDPR-9": {
        "processes_personal_data": {"margin": 0.1},
        "data_is_special_category": {"margin": None},
    }}}
    idx = load_element_index("GDPR-9", emb, margins=margins)
    assert idx.full_match_disabled is True
