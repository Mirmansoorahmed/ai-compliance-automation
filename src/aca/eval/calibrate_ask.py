"""Calibrate the per-concept similarity ASK thresholds (Phase A).

Sweeps candidate ``ask_threshold`` values per concept on the TUNING set only
(eval/cases + eval/tuning_v2) and picks, for each concept, the LOWEST threshold
that keeps the benign-routed-to-ASK rate on tuning at or below a cap (default
0.15). Writes the chosen thresholds back into policy/data/thresholds.json and a
sweep table to eval/results/ask-calibration-*.json.

Safety:
- It NEVER reads eval/heldout or eval/heldout_v2 — a guard raises if a held-out
  path is ever passed in. Calibration must not see the held-out texts.
- It only sets ``ask_threshold``; it does not touch ``low``/``high``/
  ``min_elements`` or the BLOCK path.

Works with the real MiniLM model (owner runs it) and the hashed embedder (tests
and CI). The margin used is the same stage-1 margin the adapter uses
(pos_sim - neg_sim), computed WITHOUT the similarity tier so the sweep is over
the raw confidence.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from aca.guard.adapters.local_embeddings import DEFAULT_CONCEPTS, LocalEmbeddingsAdapter
from aca.guard.embeddings import build_embedder
from aca.guard.event import Event
from aca.register.yamlio import load_yaml

_EVAL_DIR = Path(__file__).resolve().parents[3] / "eval"
_TUNING_DIRS = (_EVAL_DIR / "cases", _EVAL_DIR / "tuning_v2")
_THRESHOLDS_PATH = Path(__file__).resolve().parents[3] / "policy" / "data" / "thresholds.json"
_RESULTS_DIR = _EVAL_DIR / "results"

# The cap is on the COMBINED benign hard-review rate: benign cases routed to ASK
# OR four-eyes on tuning (Fix #3/#4). four-eyes comes from a full element match,
# so the ASK threshold is calibrated ON TOP of the final element-margin regime.
DEFAULT_BENIGN_REVIEW_CAP = 0.15
DEFAULT_BENIGN_ASK_CAP = DEFAULT_BENIGN_REVIEW_CAP  # back-compat alias
# Candidate thresholds swept (coarse grid; the owner can refine).
_GRID = [round(x / 100, 2) for x in range(5, 100, 5)]  # 0.05 .. 0.95


class HeldOutAccessError(RuntimeError):
    """Raised if calibration is ever pointed at a held-out directory."""


def _assert_not_heldout(path: Path) -> None:
    parts = {p.lower() for p in path.parts}
    if any("heldout" in p or p == "held_out" for p in parts):
        raise HeldOutAccessError(
            f"calibration must not read held-out data: {path} — tune on eval/cases + eval/tuning_v2 only")


def _load_tuning_cases(dirs=_TUNING_DIRS) -> list[dict]:
    cases: list[dict] = []
    for d in dirs:
        _assert_not_heldout(d)
        if not d.exists():
            continue
        for p in sorted(d.glob("*.yaml")):
            cases.append(load_yaml(p))
    return cases


_CURVE_CAPS = [0.10, 0.15, 0.20, 0.30]


def _case_cache(emb, concepts, cases, element_margins):
    """Precompute, once, each concept's label facts per case with the ASK tier
    OFF (ask_thresholds={}). The ASK threshold only decides whether a non-full,
    high-confidence label becomes similarity_only / partial, which is pure
    arithmetic on these cached facts — so the joint sweep needs no model re-run.

    Returns a list (per case) of {concept_id: (confidence, full_match, partial_elig)}
    where ``partial_elig`` is True when >=2 of the concept's official elements
    are met but not all (a partial becomes ASK iff confidence >= the threshold).
    Full matches (four-eyes) and deny are threshold-independent and captured as
    ``full_match``.
    """
    adapter = LocalEmbeddingsAdapter(embedder=emb, concepts=tuple(concepts),
                                     ask_thresholds={}, element_margins=element_margins)
    cache = []
    for c in cases:
        labels = adapter.detect(Event(text=c.get("text", ""), language=c.get("lang")))
        row = {}
        for l in labels:
            total = l.get("elements_total") or 0
            official = set(l.get("official_elements") or [])
            met = len(set(l.get("elements_met") or []) & official) if official else len(l.get("elements_met") or [])
            full = bool(total and met >= total)
            partial_elig = (not full) and met >= 2 and total >= 3
            row[l["concept_id"]] = (float(l.get("confidence", 0.0)), full, partial_elig)
        cache.append(row)
    return cache


def _tier_for_case(facts: dict, thresholds: dict) -> str:
    """Resolve the tier for one case from cached facts + an ASK-threshold map.
    Mirrors compliance.tier: four-eyes on a full match; ASK on similarity_only
    (conf >= threshold, not full) or a partial that also clears the threshold."""
    best = "allow"
    order = {"allow": 0, "ask": 1, "four-eyes": 2, "deny": 3}
    for cid, (conf, full, _partial_elig) in facts.items():
        th = thresholds.get(cid)
        if full:
            cand = "four-eyes"
        elif th is not None and conf >= th:
            # Not a full match but confidence clears the threshold -> the adapter
            # sets similarity_only (and gates partial on the same threshold), so
            # the tier is ASK.
            cand = "ask"
        else:
            cand = "allow"
        if order[cand] > order[best]:
            best = cand
    return best


def _review_frac(cache, thresholds) -> float:
    if not cache:
        return 0.0
    return sum(1 for facts in cache
               if _tier_for_case(facts, thresholds) in ("ask", "four-eyes", "deny")) / len(cache)


def calibrate(*, benign_review_cap: float = DEFAULT_BENIGN_REVIEW_CAP,
              concepts: tuple[str, ...] = DEFAULT_CONCEPTS,
              embedder=None, element_margins: dict | None = None,
              **kwargs) -> dict:
    """Calibrate the similarity ASK thresholds JOINTLY (Fix #1).

    All 13 concepts run on every text at runtime, so the ASK thresholds are
    chosen together: the objective is the COMBINED benign->(ASK+four-eyes) rate
    across all concepts on the tuning benign set <= cap, while maximising review
    recall (attacks routed to a human). The per-case concept facts are computed
    ONCE (model run) and cached; the greedy joint sweep is then pure arithmetic.

    If the cap is unreachable even with all thresholds maxed, the thresholds stay
    maxed (fewest ASKs) and the tradeoff curve (cap -> review recall) is written.
    """
    if "benign_ask_cap" in kwargs and kwargs["benign_ask_cap"] is not None:
        benign_review_cap = kwargs["benign_ask_cap"]
    emb = embedder or build_embedder(allow_hashed_fallback=True, dim=256)

    all_cases = _load_tuning_cases()
    benign = [c for c in all_cases if c.get("category") in ("benign", "ambiguous")]
    attacks = [c for c in all_cases if c.get("expect_pattern")]
    clist = list(concepts)
    top = _GRID[-1]

    benign_cache = _case_cache(emb, clist, benign, element_margins)
    attack_cache = _case_cache(emb, clist, attacks, element_margins)

    def solve(cap):
        thr = {c: top for c in clist}
        cur_recall = _review_frac(attack_cache, thr)
        improved = True
        while improved:
            improved = False
            best = None
            for c in clist:
                lower = [g for g in _GRID if g < thr[c]]
                if not lower:
                    continue
                cand = dict(thr)
                cand[c] = lower[-1]
                if _review_frac(benign_cache, cand) > cap:
                    continue
                r = _review_frac(attack_cache, cand)
                if r > cur_recall and (best is None or r > best[1]):
                    best = (c, r, cand)
            if best is not None:
                _c, r, cand = best
                thr, cur_recall = cand, r
                improved = True
        return thr, cur_recall, _review_frac(benign_cache, thr)

    chosen_thr, recall_at_cap, benign_at_cap = solve(benign_review_cap)

    curve = []
    for cap in sorted(set(_CURVE_CAPS + [benign_review_cap])):
        _thr, rec, ben = solve(cap)
        curve.append({"cap": cap, "review_recall": round(rec, 4),
                      "benign_review_rate": round(ben, 4)})

    backend = "sentence-transformers" if str(emb.version).startswith("st:") else "hashed-fallback"
    pos_n = {c: sum(1 for x in all_cases if x.get("concept_id") == c and x.get("expect_pattern"))
             for c in clist}
    neg_n = {c: sum(1 for x in all_cases if x.get("concept_id") == c and not x.get("expect_pattern"))
             for c in clist}
    return {
        "schema": "ask-calibration/v3-joint",
        "generated_ts": time.time(),
        "embedder": emb.version,
        "embedder_backend": backend,
        "is_smoke": backend == "hashed-fallback",
        "benign_review_cap": benign_review_cap,
        "cap_measures": "benign routed to ASK + four-eyes (combined, ALL concepts jointly) on tuning",
        "joint": True,
        "achieved_benign_review_rate": round(benign_at_cap, 4),
        "achieved_review_recall": round(recall_at_cap, 4),
        "cap_unreachable": benign_at_cap > benign_review_cap,
        "tradeoff_curve": curve,
        "concepts": {c: {
            "chosen_ask_threshold": chosen_thr[c] if chosen_thr[c] < top else None,
            "n_pos": pos_n[c], "n_neg": neg_n[c],
            "note": "" if chosen_thr[c] < top else "left at max (no ASK) by the joint cap",
        } for c in clist},
    }



def write_thresholds(report: dict, *, thresholds_path: Path | None = None) -> Path:
    path = thresholds_path or _THRESHOLDS_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    th = data["thresholds"]
    for cid, info in report["concepts"].items():
        chosen = info["chosen_ask_threshold"]
        if cid in th and chosen is not None:
            th[cid]["ask_threshold"] = chosen
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def write_report(report: dict, *, results_dir: Path | None = None) -> Path:
    base = results_dir or _RESULTS_DIR
    base.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(report.get("generated_ts", 0)))
    tag = "smoke" if report.get("is_smoke") else "model"
    path = base / f"ask-calibration-{stamp}-{tag}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI glue
    import argparse

    p = argparse.ArgumentParser(prog="python -m aca.eval.calibrate_ask",
                                description="Calibrate per-concept similarity ASK thresholds on the tuning set.")
    p.add_argument("--cap", type=float, default=DEFAULT_BENIGN_REVIEW_CAP,
                   help="max benign review rate (ASK + four-eyes combined) on tuning (default 0.15)")
    p.add_argument("--write-thresholds", action="store_true",
                   help="write the chosen thresholds back into policy/data/thresholds.json")
    args = p.parse_args(argv)

    report = calibrate(benign_review_cap=args.cap)
    path = write_report(report)
    print("ASK-threshold calibration (JOINT; tuning only; cap on benign ASK + four-eyes, all concepts)")
    print(f"  embedder: {report['embedder']}  cap(benign review) <= {report['benign_review_cap']}")
    print(f"  achieved: benign_review={report['achieved_benign_review_rate']} "
          f"review_recall={report['achieved_review_recall']}"
          + ("  (cap UNREACHABLE — thresholds left at max)" if report["cap_unreachable"] else ""))
    print(f"  report: {path}")
    if report["is_smoke"]:
        print("  NOTE: hashed embedder — smoke only; run with the model for real thresholds.")
    print("  tradeoff curve (cap -> review recall @ benign review rate):")
    for row in report["tradeoff_curve"]:
        print(f"    cap<={row['cap']}: review_recall={row['review_recall']} "
              f"benign_review={row['benign_review_rate']}")
    for cid, info in report["concepts"].items():
        print(f"    {cid:12} chosen_ask_threshold={info['chosen_ask_threshold']} "
              f"(pos={info['n_pos']} neg={info['n_neg']}){' — ' + info['note'] if info['note'] else ''}")
    if args.write_thresholds:
        tp = write_thresholds(report)
        print(f"  wrote thresholds -> {tp}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
