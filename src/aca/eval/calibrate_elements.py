"""Calibrate per-element similarity margins (Phase C, revised).

Goal (Fix #1): choose per-element margins so that, on the TUNING set only, a
concept's FULL element match never fires on a case that should not be a full
match for that concept — counting CROSS-CONCEPT cases too. A benign case, or a
case about a *different* concept, that marks every element of concept X is a
false full match for X and must be driven to 0.

Key properties:
- Margins are strictly > 0 (a configurable floor, default 0.05); a 0.0 margin
  over-marks and is never chosen.
- Scoring uses the EXACT element set the runtime adapter produces, including the
  stage-0 keyword union for AIA-5-1-c, by running the real adapter with the
  candidate margins injected (not a separate re-implementation).
- The false-full-match set for concept X is: every tuning case that is NOT a
  positive of X (i.e. benign, ambiguous, or a positive of another concept).
- If no assignment at/above the floor drives X's false-full-match rate to 0, X's
  full match is DISABLED (an element margin set null) so it falls back to the
  Phase A ASK tier. Disabled concepts are listed.

Safety: never reads eval/heldout or eval/heldout_v2 (guard raises). Tuning =
eval/cases + eval/tuning_v2 only. Works with the real model (owner) and the
hashed embedder (tests).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from aca.eval.calibrate_ask import HeldOutAccessError, _assert_not_heldout
from aca.guard.adapters.local_embeddings import DEFAULT_CONCEPTS, LocalEmbeddingsAdapter
from aca.guard.embeddings import build_embedder
from aca.guard.event import Event
from aca.guard.stages.elements import load_element_index
from aca.register.yamlio import load_yaml

_EVAL_DIR = Path(__file__).resolve().parents[3] / "eval"
_TUNING_DIRS = (_EVAL_DIR / "cases", _EVAL_DIR / "tuning_v2")
_MARGINS_PATH = Path(__file__).resolve().parents[3] / "policy" / "data" / "element_margins.json"
_RESULTS_DIR = _EVAL_DIR / "results"

DEFAULT_FLOOR = 0.05
# Candidate margins swept — all strictly above 0 (>= the floor).
_GRID = [round(x / 100, 2) for x in range(5, 80, 3)]  # 0.05 .. 0.77

MIN_TUNING_POSITIVES = 6  # Fix #5: warn below this


def _load_tuning_cases() -> list[dict]:
    cases: list[dict] = []
    for d in _TUNING_DIRS:
        _assert_not_heldout(d)
        if d.exists():
            for p in sorted(d.glob("*.yaml")):
                cases.append(load_yaml(p))
    return cases


def _margins_for(index_elements, assignment: dict[str, float | None]) -> dict:
    """A margins-file-shaped dict for one concept with a candidate assignment."""
    return {e: {"margin": assignment[e]} for e in index_elements}


def _element_margin_vec(emb, index, text: str) -> dict[str, float]:
    """Raw pos-neg similarity margin per element for one text (no threshold)."""
    from aca.guard.stages.elements import _max_sim
    qvec = emb.embed(text)
    return {e: _max_sim(qvec, ex.positives) - _max_sim(qvec, ex.negatives)
            for e, ex in index.elements.items()}


def _adapter_elements_for_concept(emb, concept_id, margins_dict, texts):
    """Run the REAL adapter (with these margins) and return, per text, the set of
    elements it marks for ``concept_id`` — i.e. exactly the runtime element set,
    including the AIA-5-1-c stage-0 keyword union."""
    adapter = LocalEmbeddingsAdapter(embedder=emb, concepts=(concept_id,),
                                     ask_thresholds={},
                                     element_margins={"concepts": {concept_id: margins_dict},
                                                      "default_margin": DEFAULT_FLOOR})
    out = []
    for t in texts:
        labels = adapter.detect(Event(text=t))
        label = next((l for l in labels if l["concept_id"] == concept_id), None)
        out.append(set(label.get("elements_met", [])) if label else set())
    return out


def calibrate(*, concepts: tuple[str, ...] = DEFAULT_CONCEPTS, embedder=None,
              floor: float = DEFAULT_FLOOR) -> dict:
    emb = embedder or build_embedder(allow_hashed_fallback=True, dim=256)
    all_cases = _load_tuning_cases()

    out_concepts: dict[str, dict] = {}
    for cid in concepts:
        index = load_element_index(cid, emb, margins={})
        if index is None:
            continue
        elements = list(index.elements.keys())

        pos_cases = [c for c in all_cases if c.get("concept_id") == cid and c.get("expect_pattern")]
        # Everything that must NOT be a full match of X: benign/ambiguous of any
        # concept, plus positives of OTHER concepts (cross-concept false matches).
        nonpos_cases = [c for c in all_cases
                        if not (c.get("concept_id") == cid and c.get("expect_pattern"))]
        pos_texts = [c.get("text", "") for c in pos_cases]
        nonpos_texts = [c.get("text", "") for c in nonpos_cases]

        # Raw per-element margins for positives and non-positives (used to pick a
        # per-element starting threshold that still marks positives).
        pos_vecs = [_element_margin_vec(emb, index, t) for t in pos_texts]

        # Start each element at the floor; raise the threshold to break any
        # false full match, checking the REAL adapter element set (with the
        # stage-0 union) each round.
        chosen: dict[str, float | None] = {e: floor for e in elements}

        def false_full_count(assignment):
            marks = _adapter_elements_for_concept(
                emb, cid, _margins_for(elements, assignment), nonpos_texts)
            req = set(elements)
            return sum(1 for m in marks if req.issubset(m))

        def pos_full_count(assignment):
            marks = _adapter_elements_for_concept(
                emb, cid, _margins_for(elements, assignment), pos_texts)
            req = set(elements)
            return sum(1 for m in marks if req.issubset(m))

        disabled: list[str] = []
        guard = 0
        while guard < 300:
            guard += 1
            if false_full_count(chosen) == 0:
                break
            # Raise the element whose current margin is lowest (cheapest to
            # tighten). If it is already at grid max, disable it (null) and stop.
            active = [e for e in elements if chosen[e] is not None]
            if not active:
                break
            cand = min(active, key=lambda e: chosen[e])
            higher = [g for g in _GRID if g > chosen[cand]]
            if higher:
                chosen[cand] = higher[0]
            else:
                chosen[cand] = None
                disabled.append(cand)
                break

        ffc = false_full_count(chosen)
        pfc = pos_full_count(chosen) if not disabled else 0
        # Fix #5: stability warnings.
        warnings = []
        if len(pos_cases) < MIN_TUNING_POSITIVES:
            warnings.append(f"only {len(pos_cases)} tuning positives (< {MIN_TUNING_POSITIVES})")
        if pfc == 0 and not disabled:
            warnings.append("0 tuning positives reach a full match at the chosen margins "
                            "(strict recall will be 0 — data or element design)")

        out_concepts[cid] = {e: {"margin": chosen[e]} for e in elements}
        out_concepts[cid]["_meta"] = {
            "false_full_match_rate_tuning": round(ffc / len(nonpos_texts), 4) if nonpos_texts else 0.0,
            "pos_full_match_count": pfc,
            "n_pos": len(pos_cases),
            "n_nonpos": len(nonpos_texts),
            "disabled_elements": disabled,
            "full_match_disabled": bool(disabled),
            "warnings": warnings,
            "floor": floor,
        }

    backend = "sentence-transformers" if str(emb.version).startswith("st:") else "hashed-fallback"
    return {
        "schema": "element-margins/v2",
        "generated_ts": time.time(),
        "embedder": emb.version,
        "embedder_backend": backend,
        "is_smoke": backend == "hashed-fallback",
        "floor": floor,
        "default_margin": floor,
        "concepts": out_concepts,
    }


def write_margins(report: dict, *, margins_path: Path | None = None) -> Path:
    path = margins_path or _MARGINS_PATH
    doc = {
        "_doc": ("Per-element similarity margins for Phase C. Calibrated on the tuning set "
                 "only; margins are strictly > 0 (floor). A concept's full match fires only "
                 "when EVERY element clears its margin; calibration drives the tuning "
                 "false-full-match rate (incl. cross-concept) to 0, else the concept's full "
                 "match is disabled (an element margin null -> falls back to the ASK tier). "
                 "Regenerate with the single calibrate command (see docs/v2/DETECTION-DIAGNOSIS.md)."),
        "default_margin": report.get("default_margin", DEFAULT_FLOOR),
        "concepts": {cid: {k: v for k, v in info.items() if k != "_meta"}
                     for cid, info in report["concepts"].items()},
    }
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def write_report(report: dict, *, results_dir: Path | None = None) -> Path:
    base = results_dir or _RESULTS_DIR
    base.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(report.get("generated_ts", 0)))
    tag = "smoke" if report.get("is_smoke") else "model"
    path = base / f"element-margins-{stamp}-{tag}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI glue
    import argparse

    p = argparse.ArgumentParser(prog="python -m aca.eval.calibrate_elements",
                                description="Calibrate per-element similarity margins on the tuning set.")
    p.add_argument("--write-margins", action="store_true",
                   help="write the calibrated margins into policy/data/element_margins.json")
    p.add_argument("--floor", type=float, default=DEFAULT_FLOOR,
                   help="minimum per-element margin (strictly > 0; default 0.05)")
    args = p.parse_args(argv)

    report = calibrate(floor=args.floor)
    path = write_report(report)
    print("Element-margin calibration (tuning only; cross-concept false-full-match target = 0)")
    print(f"  embedder: {report['embedder']}  floor={report['floor']}")
    print(f"  report: {path}")
    if report["is_smoke"]:
        print("  NOTE: hashed embedder — smoke only; run with the model for real margins.")
    for cid, info in report["concepts"].items():
        meta = info["_meta"]
        flag = " FULL-MATCH DISABLED" if meta["full_match_disabled"] else ""
        warn = ("  !! " + "; ".join(meta["warnings"])) if meta["warnings"] else ""
        print(f"    {cid:12} false_full_match={meta['false_full_match_rate_tuning']} "
              f"pos_full={meta['pos_full_match_count']}/{meta['n_pos']}{flag}{warn}")
    if args.write_margins:
        mp = write_margins(report)
        print(f"  wrote margins -> {mp}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
