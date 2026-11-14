"""Metrics discipline helpers (R12.3).

No number in a README, report, or CV bullet may be invented. Every figure must
come from a committed eval run with a timestamp and git SHA. These helpers load
the latest committed run and format metrics with their provenance, or render
``TO BE MEASURED`` when no committed run exists.

``IMPORTANT``: the committed oss run uses the deterministic hashed-vector
embedding fallback, not a trained model, so its precision/recall/latency are a
reproducible baseline — NOT a claim about real detector quality. Reports label
the embedder used so this is explicit.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

_RESULTS = Path(__file__).resolve().parents[3] / "eval" / "results"

TO_BE_MEASURED = "TO BE MEASURED"


def latest_run(results_dir: Path | None = None) -> dict | None:
    base = results_dir or _RESULTS
    latest = base / "latest.json"
    if latest.exists():
        return json.loads(latest.read_text(encoding="utf-8"))
    runs = sorted(base.glob("eval-*.json"))
    if not runs:
        return None
    return json.loads(runs[-1].read_text(encoding="utf-8"))


def metric_or_to_be_measured(run: dict | None, path: list[str]) -> str:
    """Return a provenanced metric string, or TO BE MEASURED when absent."""
    if run is None:
        return TO_BE_MEASURED
    node = run
    for key in path:
        if not isinstance(node, dict) or key not in node or node[key] is None:
            return TO_BE_MEASURED
        node = node[key]
    return str(node)


def provenance_line(run: dict | None) -> str:
    if run is None:
        return f"_{TO_BE_MEASURED} — no committed eval run yet._"
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(run.get("generated_ts", 0)))
    sha = str(run.get("git_sha", "unknown"))[:8]
    embedder = run.get("embedder", "unknown")
    return f"_Source: committed eval run {stamp}, git {sha}, embedder `{embedder}`._"


def results_table(run: dict | None) -> list[str]:
    """Markdown lines for a results table, with provenance or TO BE MEASURED."""
    lines = [
        "| Metric | de | en |",
        "|---|---|---|",
    ]
    pl = (run or {}).get("per_language", {})
    for metric, key in (("Label precision", "precision"), ("Label recall", "recall")):
        de = metric_or_to_be_measured({"v": pl.get("de", {}).get(key)} if run else None, ["v"])
        en = metric_or_to_be_measured({"v": pl.get("en", {}).get(key)} if run else None, ["v"])
        lines.append(f"| {metric} | {de} | {en} |")
    fbr = metric_or_to_be_measured(run, ["benign_false_block_rate"])
    p95 = metric_or_to_be_measured(run, ["latency_ms", "stage_0_1_p95_ms"])
    lines.append(f"| Benign false-block rate | {fbr} | {fbr} |")
    lines.append(f"| Semantic path p95 (stages 0-1, ms) | {p95} | {p95} |")
    lines.append(f"| Semantic path p95 (stages 2-3, ms) | {TO_BE_MEASURED} | {TO_BE_MEASURED} |")
    return lines
