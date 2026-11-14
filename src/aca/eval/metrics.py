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


def _cell(run: dict | None, lang: str, key: str) -> str:
    if run is None:
        return TO_BE_MEASURED
    val = (run.get("per_language", {}).get(lang, {}) or {}).get(key)
    return TO_BE_MEASURED if val is None else str(val)


def _held_cell(run: dict | None, lang: str, key: str) -> str:
    if run is None:
        return TO_BE_MEASURED
    val = ((run.get("held_out", {}) or {}).get("per_language", {}).get(lang, {}) or {}).get(key)
    return TO_BE_MEASURED if val is None else str(val)


def results_table(run: dict | None) -> list[str]:
    """Markdown lines for the results table, with provenance or TO BE MEASURED.

    Reports strict label precision/recall, the routed-to-review rate (strict +
    partial-pattern routing to a human), the benign false-block and
    benign-routed-to-ask rates, latency, and the prompt-injection (vendor) row.
    """
    lines = [
        "| Metric | de | en | overall |",
        "|---|---|---|---|",
        f"| Label precision (strict) | {_cell(run, 'de', 'precision')} "
        f"| {_cell(run, 'en', 'precision')} | {_cell(run, 'overall', 'precision')} |",
        f"| Label recall (strict, full pattern) | {_cell(run, 'de', 'recall')} "
        f"| {_cell(run, 'en', 'recall')} | {_cell(run, 'overall', 'recall')} |",
        f"| Attacks routed to review (strict + partial -> ask) | {_cell(run, 'de', 'routed_to_review')} "
        f"| {_cell(run, 'en', 'routed_to_review')} | {_cell(run, 'overall', 'routed_to_review')} |",
    ]
    fbr = metric_or_to_be_measured(run, ["benign_false_block_rate"])
    ask = metric_or_to_be_measured(run, ["benign_routed_to_ask_rate"])
    p95 = metric_or_to_be_measured(run, ["latency_ms", "stage_0_1_p95_ms"])
    lines.append(f"| Benign false-block rate (strict) | | | {fbr} |")
    lines.append(f"| Benign routed-to-ask rate | | | {ask} |")
    lines.append(f"| Semantic path p95 (stages 0-1, ms) | | | {p95} |")
    lines.append(f"| Semantic path p95 (stages 2-3, ms) | | | {TO_BE_MEASURED} |")
    pi_prec = metric_or_to_be_measured(run, ["prompt_injection", "precision"])
    pi_rec = metric_or_to_be_measured(run, ["prompt_injection", "recall"])
    lines.append(f"| Prompt-injection precision (vendor path) | | | {pi_prec} |")
    lines.append(f"| Prompt-injection recall (vendor path) | | | {pi_rec} |")
    return lines


def held_out_table(run: dict | None) -> list[str]:
    """Markdown lines for the held-out results, scored separately."""
    lines = [
        "| Held-out metric | de | en | overall |",
        "|---|---|---|---|",
        f"| Label recall (strict) | {_held_cell(run, 'de', 'recall')} "
        f"| {_held_cell(run, 'en', 'recall')} | {_held_cell(run, 'overall', 'recall')} |",
        f"| Attacks routed to review | {_held_cell(run, 'de', 'routed_to_review')} "
        f"| {_held_cell(run, 'en', 'routed_to_review')} | {_held_cell(run, 'overall', 'routed_to_review')} |",
    ]
    fbr = metric_or_to_be_measured(run, ["held_out", "benign_false_block_rate"])
    lines.append(f"| Benign false-block rate | | | {fbr} |")
    return lines
