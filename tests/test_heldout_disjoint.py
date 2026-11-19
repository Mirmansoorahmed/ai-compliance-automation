"""Phase 5 eval fix — held-out sets are disjoint from exemplars + tuning.

Fails if any held-out case text (eval/heldout_v2/) or vague-law case state
(eval/vaguelaw/) also appears verbatim in an exemplar file or in the tuning set
(eval/cases/). Also checks the per-concept / per-question case counts meet the
>= 6 positives + 6 negatives bar.
"""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from aca.register.yamlio import load_yaml

_ROOT = Path(__file__).resolve().parents[1]
_EXEMPLARS = _ROOT / "exemplars"
_TUNING = _ROOT / "eval" / "cases"
_HELDOUT = _ROOT / "eval" / "heldout_v2"
_VAGUELAW = _ROOT / "eval" / "vaguelaw"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _exemplar_texts() -> set[str]:
    texts: set[str] = set()
    for p in _EXEMPLARS.glob("*.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        for group in ("positives", "hard_negatives"):
            for item in data.get(group, []):
                texts.add(_norm(item.get("text", "")))
    return texts


def _tuning_texts() -> set[str]:
    texts: set[str] = set()
    for p in _TUNING.glob("*.yaml"):
        c = load_yaml(p)
        if c.get("text"):
            texts.add(_norm(c["text"]))
        for turn in c.get("turns", []) or []:
            texts.add(_norm(turn))
    return texts


_FORBIDDEN = None


def _forbidden():
    global _FORBIDDEN
    if _FORBIDDEN is None:
        _FORBIDDEN = _exemplar_texts() | _tuning_texts()
    return _FORBIDDEN


def test_heldout_v2_disjoint_from_exemplars_and_tuning():
    forbidden = _forbidden()
    clashes = []
    for p in _HELDOUT.glob("*.yaml"):
        t = _norm(load_yaml(p).get("text", ""))
        if t and t in forbidden:
            clashes.append(p.name)
    assert not clashes, f"held-out text reused from exemplars/tuning: {clashes}"


def test_vaguelaw_disjoint_from_exemplars_and_tuning():
    forbidden = _forbidden()
    clashes = []
    for p in _VAGUELAW.glob("*.yaml"):
        t = _norm(load_yaml(p).get("state", ""))
        if t and t in forbidden:
            clashes.append(p.name)
    assert not clashes, f"vague-law text reused from exemplars/tuning: {clashes}"


def test_heldout_and_vaguelaw_have_no_internal_duplicates():
    for d, key in ((_HELDOUT, "text"), (_VAGUELAW, "state")):
        seen = Counter(_norm(load_yaml(p).get(key, "")) for p in d.glob("*.yaml"))
        dups = [t for t, n in seen.items() if n > 1 and t]
        assert not dups, f"duplicate texts within {d.name}: {len(dups)}"


def test_heldout_v2_has_six_pos_six_neg_per_concept():
    by_concept: dict = {}
    for p in _HELDOUT.glob("*.yaml"):
        c = load_yaml(p)
        d = by_concept.setdefault(c["concept_id"], {"pos": 0, "neg": 0})
        d["pos" if c["expect_pattern"] else "neg"] += 1
    assert by_concept, "no held-out v2 cases"
    for cid, d in by_concept.items():
        assert d["pos"] >= 6, f"{cid}: only {d['pos']} positives (need >= 6)"
        assert d["neg"] >= 6, f"{cid}: only {d['neg']} negatives (need >= 6)"


def test_vaguelaw_has_six_pos_six_neg_per_question_incl_new_ones():
    by_q: dict = {}
    for p in _VAGUELAW.glob("*.yaml"):
        c = load_yaml(p)
        d = by_q.setdefault(c["question_id"], {"pos": 0, "neg": 0})
        d["pos" if c["expect_yes"] else "neg"] += 1
    # The two questions that previously had no cases must now be covered.
    assert "AIA-5-1-a" in by_q
    assert "AIA-50-1" in by_q
    for qid, d in by_q.items():
        assert d["pos"] >= 6, f"{qid}: only {d['pos']} positives (need >= 6)"
        assert d["neg"] >= 6, f"{qid}: only {d['neg']} negatives (need >= 6)"


def test_both_languages_present():
    for d, key in ((_HELDOUT, "concept_id"), (_VAGUELAW, "question_id")):
        langs = {load_yaml(p).get("lang") for p in d.glob("*.yaml")}
        assert {"de", "en"} <= langs, f"{d.name} must mix de and en"
