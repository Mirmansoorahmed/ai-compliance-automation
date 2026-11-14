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


def test_eval_set_is_large_and_balanced():
    # Grown to a credible size (60-100 cases) across concepts and languages.
    cases = load_cases(CASES)
    assert 60 <= len(cases) <= 100
    aia = [c for c in cases if c.get("concept_id") == "AIA-5-1-c"]
    pi = [c for c in cases if c.get("concept_id") == "PROMPT-INJECTION"]
    assert len(aia) >= 40
    assert len(pi) >= 15
    # Every case carries a source note and an expected label.
    for c in cases:
        assert c.get("source")
        if c["concept_id"] == "PROMPT-INJECTION":
            assert "expect_injection" in c
        else:
            assert "expect_pattern" in c


def test_eval_set_has_hard_negative_and_salami():
    cases = load_cases(CASES)
    assert any(c.get("hard_negative") for c in cases)
    assert any(c.get("multi_turn") for c in cases)


def test_prompt_injection_set_has_direct_and_indirect():
    cases = load_cases(CASES)
    pi_attacks = [c for c in cases if c.get("concept_id") == "PROMPT-INJECTION" and c.get("category") == "injection"]
    pi_clean = [c for c in cases if c.get("concept_id") == "PROMPT-INJECTION" and c.get("category") == "clean"]
    assert pi_attacks and pi_clean
    ids = " ".join(c["id"] for c in pi_attacks)
    assert "direct" in ids and "indirect" in ids


def test_runner_reports_per_language_and_provenance(tmp_path):
    report = run_eval(repo_root=REPO)
    assert isinstance(report, EvalReport)
    assert report.generated_ts > 0
    assert report.git_sha  # provenance present (may be 'unknown' off-git)
    # per_language carries de, en, and an overall aggregate.
    assert {"de", "en", "overall"} <= set(report.per_language)
    for lang, m in report.per_language.items():
        assert "precision" in m and "recall" in m
    # benign false-block rate is reported (R12.1).
    assert report.benign_false_block_rate is not None
    # The run records which embedding backend produced it.
    assert report.embedder_backend in ("sentence-transformers", "hashed-fallback")


def test_prompt_injection_scored_separately_as_to_be_measured():
    report = run_eval(repo_root=REPO)
    pi = report.prompt_injection
    assert pi["n_cases"] >= 15
    assert pi["precision"] == "TO BE MEASURED"
    assert pi["recall"] == "TO BE MEASURED"


def test_routed_to_review_is_at_least_strict_recall():
    # Every full-pattern detection routes to review, and partials add to it, so
    # routed_to_review must never be below strict recall.
    report = run_eval(repo_root=REPO)
    o = report.per_language["overall"]
    assert o["routed_to_review"] >= o["recall"]


def test_held_out_set_is_scored_separately():
    report = run_eval(repo_root=REPO)
    ho = report.held_out
    assert ho["n_cases"] >= 15
    assert "per_language" in ho
    assert "overall" in ho["per_language"]
    # Held-out carries its own false-block rate.
    assert "benign_false_block_rate" in ho


def test_benign_false_block_stays_zero_and_routed_to_ask_reported():
    report = run_eval(repo_root=REPO)
    assert report.benign_false_block_rate == 0.0
    assert report.benign_routed_to_ask_rate is not None


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
    # At least one multi-turn 'salami' case accumulates elements to the full
    # pattern across turns (stage S). (The hashed fallback may miss harder
    # variants; the EN salami is the canonical one.)
    salami = next(c for c in report.cases if c["id"] == "aia-5-1-c-salami-en-2")
    assert salami["detected_pattern"] is True
