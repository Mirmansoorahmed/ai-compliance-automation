"""Phase 9 — demo smoke test (R14)."""

import json
from pathlib import Path

from aca.demo import run_demo


def test_demo_three_scenarios_outcomes(tmp_path):
    spans = tmp_path / "demo_spans.jsonl"
    outcomes = run_demo(repo=Path(__file__).resolve().parents[1], spans_path=spans)
    # Scenario 1: keyword-free social scoring -> deny.
    assert outcomes["scenario1_deny"] == "deny"
    # Scenario 2: ambiguous -> ask/four-eyes; replay after merge -> deny.
    assert outcomes["scenario2_before"] in ("ask", "four-eyes")
    assert outcomes["scenario2_after_replay"] == "deny"
    assert outcomes["scenario2_change_set"].startswith("interpretations/")
    # Scenario 3: benign hard negative -> allow.
    assert outcomes["scenario3_allow"] == "allow"


def test_demo_writes_spans(tmp_path):
    spans = tmp_path / "demo_spans.jsonl"
    run_demo(repo=Path(__file__).resolve().parents[1], spans_path=spans)
    lines = spans.read_text(encoding="utf-8").strip().splitlines()
    # 4 decisions emitted (1 + 2 + 1).
    assert len(lines) == 4
    first = json.loads(lines[0])
    assert first["attributes"]["tier"] == "deny"
    # Privacy: no clear subject id in any span.
    blob = spans.read_text(encoding="utf-8")
    assert "nordpay-user-1" not in blob


def test_demo_does_not_write_policy_data(tmp_path):
    # The change set in scenario 2 must not touch policy/.
    spans = tmp_path / "demo_spans.jsonl"
    outcomes = run_demo(repo=Path(__file__).resolve().parents[1], spans_path=spans)
    assert not outcomes["scenario2_change_set"].startswith("policy/")
