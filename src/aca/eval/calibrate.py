"""Single calibration command (Fix #4): element margins first, then ASK thresholds.

Order matters. The ASK threshold's benign cap is on the COMBINED benign hard
review rate (ASK + four-eyes), and four-eyes depends on the element margins, so
the element margins must be fixed first and the ASK thresholds calibrated on top
of that final element regime.

    python -m aca.eval.calibrate [--write] [--floor 0.05] [--cap 0.15]

Writes (with --write):
  policy/data/element_margins.json   (element margins; strictly > 0 floor)
  policy/data/thresholds.json        (ask_threshold per concept)
  eval/results/calibration-<ts>-<tag>.json  (combined report; always written)

Tuning only; never reads eval/heldout or eval/heldout_v2.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from aca.eval import calibrate_ask, calibrate_elements
from aca.guard.embeddings import resolve_embedder

_RESULTS_DIR = Path(__file__).resolve().parents[3] / "eval" / "results"


def calibrate(*, floor: float = calibrate_elements.DEFAULT_FLOOR,
              cap: float = calibrate_ask.DEFAULT_BENIGN_REVIEW_CAP,
              embedder=None, require_model: bool | None = None) -> dict:
    # Fix 3: shared loader. require_model (or ACA_REQUIRE_MODEL=1) fails loudly
    # if the real model is absent instead of silently using the hashed fallback.
    emb = embedder or resolve_embedder(require_model=require_model, dim=256)

    # 1. Element margins first (cross-concept false-full-match -> 0, or disable).
    elem = calibrate_elements.calibrate(embedder=emb, floor=floor)
    # Shape the chosen margins the way the adapter expects, to feed step 2.
    element_margins = {
        "default_margin": elem.get("default_margin", floor),
        "concepts": {cid: {k: v for k, v in info.items() if k != "_meta"}
                     for cid, info in elem["concepts"].items()},
    }

    # 2. ASK thresholds ON TOP of the final element regime; cap on ASK+four-eyes.
    ask = calibrate_ask.calibrate(benign_review_cap=cap, embedder=emb,
                                  element_margins=element_margins)

    backend = "sentence-transformers" if str(emb.version).startswith("st:") else "hashed-fallback"
    return {
        "schema": "calibration/v1",
        "generated_ts": time.time(),
        "embedder": emb.version,
        "embedder_backend": backend,
        "is_smoke": backend == "hashed-fallback",
        "floor": floor,
        "benign_review_cap": cap,
        "order": "element margins calibrated first, then ASK thresholds on top",
        "element_margins": elem,
        "ask_thresholds": ask,
    }


def write_report(report: dict, *, results_dir: Path | None = None) -> Path:
    base = results_dir or _RESULTS_DIR
    base.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(report.get("generated_ts", 0)))
    tag = "smoke" if report.get("is_smoke") else "model"
    path = base / f"calibration-{stamp}-{tag}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI glue
    import argparse

    p = argparse.ArgumentParser(
        prog="python -m aca.eval.calibrate",
        description="Calibrate element margins then ASK thresholds (tuning only, one command).")
    p.add_argument("--write", action="store_true",
                   help="write element_margins.json and thresholds.json")
    p.add_argument("--floor", type=float, default=calibrate_elements.DEFAULT_FLOOR,
                   help="minimum per-element margin (strictly > 0; default 0.05)")
    p.add_argument("--cap", type=float, default=calibrate_ask.DEFAULT_BENIGN_REVIEW_CAP,
                   help="max benign review rate (ASK + four-eyes) on tuning (default 0.15)")
    p.add_argument("--require-model", action="store_true",
                   help="fail loudly if the real sentence-transformers model is not available "
                        "(also via ACA_REQUIRE_MODEL=1)")
    args = p.parse_args(argv)

    report = calibrate(floor=args.floor, cap=args.cap,
                       require_model=True if args.require_model else None)
    path = write_report(report)
    print("Combined calibration (tuning only): element margins -> ASK thresholds")
    print(f"  embedder: {report['embedder']}  floor={report['floor']}  "
          f"benign-review cap <= {report['benign_review_cap']}")
    print(f"  report: {path}")
    if report["is_smoke"]:
        print("  NOTE: hashed embedder — smoke only; run with the model for real values.")
    for cid, info in report["element_margins"]["concepts"].items():
        meta = info["_meta"]
        ask = report["ask_thresholds"]["concepts"].get(cid, {})
        flag = " FULL-MATCH DISABLED" if meta["full_match_disabled"] else ""
        warn = ("  !! " + "; ".join(meta["warnings"])) if meta["warnings"] else ""
        print(f"    {cid:12} false_full_match={meta['false_full_match_rate_tuning']} "
              f"pos_full={meta['pos_full_match_count']}/{meta['n_pos']} "
              f"ask_threshold={ask.get('chosen_ask_threshold')}{flag}{warn}")

    if args.write:
        mp = calibrate_elements.write_margins(report["element_margins"])
        tp = calibrate_ask.write_thresholds(report["ask_thresholds"])
        print(f"  wrote {mp}")
        print(f"  wrote {tp}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
