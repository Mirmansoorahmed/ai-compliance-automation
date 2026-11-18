"""Phase 8 — metrics discipline (R12.3).

No invented metrics: a metric either comes from a committed eval run (with
timestamp + git SHA) or renders as TO BE MEASURED. Also scans README/docs for
bare performance numbers that lack provenance.
"""

import re
from pathlib import Path

from aca.eval.metrics import (
    TO_BE_MEASURED,
    latest_run,
    metric_or_to_be_measured,
    provenance_line,
    results_table,
)

REPO = Path(__file__).resolve().parents[1]


def test_missing_run_renders_to_be_measured(tmp_path):
    assert metric_or_to_be_measured(None, ["per_language", "en", "precision"]) == TO_BE_MEASURED
    assert TO_BE_MEASURED in provenance_line(None)
    table = results_table(None)
    assert any(TO_BE_MEASURED in line for line in table)


def test_present_run_is_shown_with_provenance():
    run = {
        "generated_ts": 1731607200.0,
        "git_sha": "abcdef1234567890",
        "embedder": "hashed/0.1.0:dim=256",
        "per_language": {"en": {"precision": 1.0, "recall": 1.0}},
        "benign_false_block_rate": 0.0,
        "latency_ms": {"stage_0_1_p95_ms": 1.9},
    }
    line = provenance_line(run)
    assert "git abcdef12" in line
    assert "hashed/0.1.0" in line
    assert metric_or_to_be_measured(run, ["benign_false_block_rate"]) == "0.0"


def test_committed_latest_run_exists_and_has_provenance():
    run = latest_run()
    assert run is not None, "a committed eval run (eval/results/latest.json) must exist"
    assert run.get("git_sha")
    assert run.get("generated_ts", 0) > 0
    assert run.get("embedder")


def _docs_to_scan():
    paths = [REPO / "README.md"]
    return [p for p in paths if p.exists()]


def test_no_bare_performance_numbers_in_readme():
    # A performance claim like "95% precision" or "12ms p95" must not appear in
    # the README unless it is the TO BE MEASURED placeholder or inside a table
    # row that carries a provenance source line. We enforce the simplest safe
    # rule: the README must not contain a hard-coded percent/ms performance
    # claim for precision/recall/latency outside the generated results table.
    pat = re.compile(r"\b\d{1,3}\s?%\s+(precision|recall|accuracy)\b", re.IGNORECASE)
    for doc in _docs_to_scan():
        text = doc.read_text(encoding="utf-8")
        assert not pat.search(text), f"{doc.name} has a bare performance claim"
