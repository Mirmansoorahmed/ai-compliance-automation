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
from dataclasses import dataclass
from pathlib import Path

from aca.guard.adapters.local_embeddings import DEFAULT_CONCEPTS, LocalEmbeddingsAdapter
from aca.guard.embeddings import build_embedder
from aca.guard.event import Event
from aca.policy.decide import PolicyData, decide, load_policy_data
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


@dataclass
class ConceptSweep:
    concept_id: str
    chosen: float | None
    rows: list[dict]
    n_pos: int
    n_neg: int
    note: str = ""


def _load_tuning_cases(dirs=_TUNING_DIRS) -> list[dict]:
    cases: list[dict] = []
    for d in dirs:
        _assert_not_heldout(d)
        if not d.exists():
            continue
        for p in sorted(d.glob("*.yaml")):
            cases.append(load_yaml(p))
    return cases


def _benign_hard_review_rate(emb, policy, concept_id, ask_threshold, neg_cases, element_margins) -> float:
    """Fraction of this concept's benign tuning cases routed to ASK OR four-eyes
    when ``concept_id`` uses ``ask_threshold`` — measured through the REAL
    adapter (with the final element margins) + decide(). four-eyes can only come
    from a full element match; ASK from the similarity/partial/low path."""
    adapter = LocalEmbeddingsAdapter(
        embedder=emb, concepts=(concept_id,),
        ask_thresholds={concept_id: ask_threshold},
        element_margins=element_margins,
    )
    hard = 0
    for c in neg_cases:
        labels = adapter.detect(Event(text=c.get("text", ""), language=c.get("lang")))
        tier = decide(labels, policy)
        if tier in ("ask", "four-eyes", "deny"):
            hard += 1
    return hard / len(neg_cases) if neg_cases else 0.0


def calibrate(*, benign_review_cap: float = DEFAULT_BENIGN_REVIEW_CAP,
              concepts: tuple[str, ...] = DEFAULT_CONCEPTS,
              embedder=None, element_margins: dict | None = None,
              **kwargs) -> dict:
    """Calibrate the similarity ASK threshold per concept ON TOP of the final
    element-margin regime (Fix #4). For each concept, pick the LOWEST threshold
    whose COMBINED benign hard-review rate (ASK + four-eyes) on tuning is <= cap.
    """
    if "benign_ask_cap" in kwargs and kwargs["benign_ask_cap"] is not None:
        benign_review_cap = kwargs["benign_ask_cap"]
    emb = embedder or build_embedder(allow_hashed_fallback=True, dim=256)
    policy = PolicyData(thresholds=load_policy_data().thresholds, confirmed_prohibited_patterns=[])

    all_cases = _load_tuning_cases()
    sweeps: list[ConceptSweep] = []
    for cid in concepts:
        pos = [c for c in all_cases if c.get("concept_id") == cid and c.get("expect_pattern")]
        neg = [c for c in all_cases if c.get("concept_id") == cid and not c.get("expect_pattern")]

        rows = []
        chosen = None
        for th in _GRID:
            benign_review = _benign_hard_review_rate(emb, policy, cid, th, neg, element_margins)
            rows.append({"threshold": th, "benign_review_rate": round(benign_review, 4)})
            if chosen is None and benign_review <= benign_review_cap:
                chosen = th
        note = "" if chosen is not None else (
            "no threshold keeps benign review (ask+four-eyes) <= cap on tuning; left unset")
        sweeps.append(ConceptSweep(cid, chosen, rows, len(pos), len(neg), note))

    backend = "sentence-transformers" if str(emb.version).startswith("st:") else "hashed-fallback"
    return {
        "schema": "ask-calibration/v2",
        "generated_ts": time.time(),
        "embedder": emb.version,
        "embedder_backend": backend,
        "is_smoke": backend == "hashed-fallback",
        "benign_review_cap": benign_review_cap,
        "cap_measures": "benign routed to ASK + four-eyes (combined) on tuning",
        "concepts": {s.concept_id: {
            "chosen_ask_threshold": s.chosen,
            "n_pos": s.n_pos, "n_neg": s.n_neg,
            "note": s.note,
            "sweep": s.rows,
        } for s in sweeps},
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
    print("ASK-threshold calibration (tuning set only; cap on benign ASK + four-eyes)")
    print(f"  embedder: {report['embedder']}  cap(benign review) <= {report['benign_review_cap']}")
    print(f"  report: {path}")
    if report["is_smoke"]:
        print("  NOTE: hashed embedder — smoke only; run with the model for real thresholds.")
    for cid, info in report["concepts"].items():
        print(f"    {cid:12} chosen_ask_threshold={info['chosen_ask_threshold']} "
              f"(pos={info['n_pos']} neg={info['n_neg']}){' — ' + info['note'] if info['note'] else ''}")
    if args.write_thresholds:
        tp = write_thresholds(report)
        print(f"  wrote thresholds -> {tp}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
