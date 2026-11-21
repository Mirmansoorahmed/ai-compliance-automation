"""Calibrate per-element similarity margins (Phase C).

For each concept and each legal element, this sweeps the margin (max-sim to the
element's positives minus max-sim to its negatives) on the TUNING set only and
picks the margin that keeps the per-concept FALSE-BLOCK rate at 0 while marking
as many true element occurrences as possible. The false-block constraint is
evaluated at the CONCEPT level: a benign tuning case is a false block if ALL of
the concept's elements are marked met for it (a full match -> BLOCK).

If no margin assignment can get the concept's tuning false-block rate to 0, the
weakest element is set to ``null`` (disabled), which turns off that concept's
full match (it falls back to the Phase A ASK tier). This is reported.

Safety: like calibrate_ask, this NEVER reads a held-out directory — a guard
raises on any held-out path. Tuning = eval/cases + eval/tuning_v2 only.

Works with the real model (owner) and the hashed embedder (tests).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from aca.eval.calibrate_ask import HeldOutAccessError, _assert_not_heldout
from aca.guard.adapters.local_embeddings import DEFAULT_CONCEPTS
from aca.guard.embeddings import build_embedder
from aca.guard.stages.elements import _max_sim, load_element_index
from aca.register.yamlio import load_yaml

_EVAL_DIR = Path(__file__).resolve().parents[3] / "eval"
_TUNING_DIRS = (_EVAL_DIR / "cases", _EVAL_DIR / "tuning_v2")
_MARGINS_PATH = Path(__file__).resolve().parents[3] / "policy" / "data" / "element_margins.json"
_RESULTS_DIR = _EVAL_DIR / "results"

_GRID = [round(x / 100, 2) for x in range(0, 60, 2)]  # 0.00 .. 0.58


def _load_tuning_cases() -> list[dict]:
    cases: list[dict] = []
    for d in _TUNING_DIRS:
        _assert_not_heldout(d)
        if d.exists():
            for p in sorted(d.glob("*.yaml")):
                cases.append(load_yaml(p))
    return cases


def _element_margin_vec(emb, index, text: str) -> dict[str, float]:
    """pos-neg margin per element for one text."""
    qvec = emb.embed(text)
    out = {}
    for element, ex in index.elements.items():
        out[element] = _max_sim(qvec, ex.positives) - _max_sim(qvec, ex.negatives)
    return out


def calibrate(*, concepts: tuple[str, ...] = DEFAULT_CONCEPTS, embedder=None) -> dict:
    emb = embedder or build_embedder(allow_hashed_fallback=True, dim=256)
    all_cases = _load_tuning_cases()

    out_concepts: dict[str, dict] = {}
    for cid in concepts:
        index = load_element_index(cid, emb, margins={})
        if index is None:
            continue
        pos = [c for c in all_cases if c.get("concept_id") == cid and c.get("expect_pattern")]
        neg = [c for c in all_cases if c.get("concept_id") == cid and not c.get("expect_pattern")]
        pos_m = [_element_margin_vec(emb, index, c.get("text", "")) for c in pos]
        neg_m = [_element_margin_vec(emb, index, c.get("text", "")) for c in neg]
        elements = list(index.elements.keys())

        # Per element: the highest margin on the grid still marks a positive if
        # its pos-margin >= threshold. We want to mark true elements (high recall)
        # while the CONCEPT-level full match stays false on every benign case.
        # Strategy: for each element pick the LOWEST grid margin whose benign
        # "element met" rate is minimised; then check concept-level false block.
        chosen: dict[str, float | None] = {}
        for i, element in enumerate(elements):
            # Choose the smallest margin that marks >=1 positive (recall) if one
            # exists; ties broken toward fewer benign marks.
            best = None
            for th in _GRID:
                pos_marks = sum(1 for m in pos_m if m[element] >= th)
                neg_marks = sum(1 for m in neg_m if m[element] >= th)
                if pos_marks >= 1:
                    best = th if best is None else best
            chosen[element] = best if best is not None else 0.0

        # Concept-level false-block check: a benign case is a false block if ALL
        # elements are marked met. Raise the margins until that is 0, element by
        # element (raise the element that most benign false-blocks share).
        def benign_fullmatch(margins: dict[str, float | None]) -> list[int]:
            fulls = []
            for j, m in enumerate(neg_m):
                if all(margins[e] is not None and m[e] >= margins[e] for e in elements):
                    fulls.append(j)
            return fulls

        disabled: list[str] = []
        guard = 0
        while True:
            guard += 1
            fulls = benign_fullmatch(chosen)
            if not fulls or guard > 200:
                break
            # Raise the element that is "closest" across the offending benign
            # cases (smallest slack), to break the full match with least harm.
            # If it is already at grid max, disable it.
            offending = fulls
            # pick element whose current margin is lowest -> easiest to raise
            cand = min((e for e in elements if chosen[e] is not None),
                       key=lambda e: chosen[e], default=None)
            if cand is None:
                break
            cur = chosen[cand]
            higher = [g for g in _GRID if g > cur]
            if higher:
                chosen[cand] = higher[0]
            else:
                chosen[cand] = None  # disable this element -> disables full match
                disabled.append(cand)
                break

        fulls = benign_fullmatch(chosen)
        false_block_rate = round(len(fulls) / len(neg_m), 4) if neg_m else 0.0
        out_concepts[cid] = {
            element: {"margin": chosen[element]} for element in elements
        }
        out_concepts[cid]["_meta"] = {
            "false_block_rate_tuning": false_block_rate,
            "disabled_elements": disabled,
            "full_match_disabled": bool(disabled),
            "n_pos": len(pos), "n_neg": len(neg),
        }

    backend = "sentence-transformers" if str(emb.version).startswith("st:") else "hashed-fallback"
    return {
        "schema": "element-margins/v1",
        "generated_ts": time.time(),
        "embedder": emb.version,
        "embedder_backend": backend,
        "is_smoke": backend == "hashed-fallback",
        "default_margin": 0.05,
        "concepts": out_concepts,
    }


def write_margins(report: dict, *, margins_path: Path | None = None) -> Path:
    path = margins_path or _MARGINS_PATH
    doc = {
        "_doc": ("Per-element similarity margins for Phase C. Calibrated on the tuning set "
                 "only; concept-level tuning false-block rate is 0 unless an element is "
                 "disabled (margin null), which turns off that concept's full match. "
                 "Regenerate with python -m aca.eval.calibrate_elements --write-margins."),
        "default_margin": report.get("default_margin", 0.05),
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
    args = p.parse_args(argv)

    report = calibrate()
    path = write_report(report)
    print("Element-margin calibration (tuning set only; concept false-block target = 0)")
    print(f"  embedder: {report['embedder']}")
    print(f"  report: {path}")
    if report["is_smoke"]:
        print("  NOTE: hashed embedder — smoke only; run with the model for real margins.")
    for cid, info in report["concepts"].items():
        meta = info["_meta"]
        flag = " FULL-MATCH DISABLED" if meta["full_match_disabled"] else ""
        print(f"    {cid:12} tuning_false_block={meta['false_block_rate_tuning']}{flag}")
    if args.write_margins:
        mp = write_margins(report)
        print(f"  wrote margins -> {mp}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
