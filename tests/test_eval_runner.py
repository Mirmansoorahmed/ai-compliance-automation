"""Phase 8 — eval set + runner tests (R11.2, R12)."""

from pathlib import Path

from aca.eval.runner import EvalReport, load_cases, run_eval, write_report

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "eval" / "cases"


def test_eval_set_has_categories_and_both_languages():
    cases = load_cases(CASES)
    assert cases
    cats = {c.get("category") for c in cases}
    langs = {c.get("lang") for c in cases}
    assert {"attack", "benign", "ambiguous"} <= cats
    assert {"de", "en"} <= langs


def test_eval_set_has_hard_negative_and_salami():
    cases = load_cases(CASES)
    assert any(c.get("hard_negative") for c in cases)
    assert any(c.get("multi_turn") for c in cases)


def test_runner_reports_per_language_and_provenance(tmp_path):
    report = run_eval(repo_root=REPO)
    assert isinstance(report, EvalReport)
    assert report.generated_ts > 0
    assert report.git_sha  # provenance present (may be 'unknown' off-git)
    assert set(report.per_language) == {"de", "en"}
    for lang, m in report.per_language.items():
        assert "precision" in m and "recall" in m
    # benign false-block rate is reported (R12.1).
    assert report.benign_false_block_rate is not None


def test_runner_scores_vendor_path_separately_null_on_oss():
    report = run_eval(repo_root=REPO)
    # Vendor/judge path is off on oss -> reported separately as null / not measured.
    assert report.vendor_path is None
    assert report.latency_ms["stage_2_3_p95_ms"] is None
    assert "not measured" in report.latency_ms["stage_2_3_note"]


def test_write_report_persists_file_with_timestamp_and_sha(tmp_path):
    report = run_eval(repo_root=REPO)
    path = write_report(report, results_dir=tmp_path)
    assert path.exists()
    assert report.git_sha[:8] in path.name
    # latest.json pointer is written too.
    assert (tmp_path / "latest.json").exists()


def test_salami_case_accumulates_to_pattern():
    report = run_eval(repo_root=REPO)
    salami = next(c for c in report.cases if c["id"] == "aia-5-1-c-salami-en")
    # Multi-turn accumulation should assert the full pattern.
    assert salami["detected_pattern"] is True
