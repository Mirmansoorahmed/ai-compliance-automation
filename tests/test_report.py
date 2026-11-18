"""Phase 9 — report builder tests (R13)."""

from pathlib import Path

import pytest

from aca.report.build import (
    DISCLAIMER,
    ReportError,
    ReportInputs,
    build_report,
    gather_inputs,
    render_text,
)
from aca.report.pdf import write_pdf

REPO = Path(__file__).resolve().parents[1]


def test_render_includes_map_coverage_and_disclaimer():
    inputs = gather_inputs(REPO)
    text = render_text(inputs)
    assert "Requirement map" in text
    assert "Coverage" in text
    assert "Semantic Guard" in text
    assert DISCLAIMER in text


def test_report_builds_valid_pdf(tmp_path):
    out = build_report(repo=REPO, out_path=tmp_path / "pack.pdf")
    data = out.read_bytes()
    assert data[:5] == b"%PDF-"
    assert b"%%EOF" in data
    assert len(data) > 1000


def test_report_fails_closed_on_missing_required_field(tmp_path):
    # A requirements dir with a row missing `title` must fail closed, no PDF.
    repo = tmp_path
    (repo / "requirements").mkdir()
    (repo / "requirements" / "bad.yaml").write_text(
        "id: REQ-BAD\nsource: EU AI Act\ncitation: Art. 5\nmode: auto\n"
        "owner: o\nstatus: active\n",  # no title
        encoding="utf-8",
    )
    (repo / "eval").mkdir()
    (repo / "eval" / "coverage_floor.json").write_text('{"pct_mapped_floor": 90.0}', encoding="utf-8")
    with pytest.raises(ReportError):
        build_report(repo=repo, out_path=tmp_path / "should-not-exist.pdf")
    assert not (tmp_path / "should-not-exist.pdf").exists()


def test_report_shows_not_measured_when_no_eval_run():
    inputs = ReportInputs(
        requirements=[{"id": "REQ-X", "citation": "Art. 5", "title": "t", "mode": "auto"}],
        coverage={"pct_mapped": 100.0, "pct_auto": 100.0, "pct_human": 0.0, "pct_hybrid": 0.0,
                  "floor": 90.0, "floor_note": "TARGET", "passes_floor": True},
        eval_run=None,
        spans=[],
    )
    text = render_text(inputs)
    assert "Not measured" in text or "TO BE MEASURED" in text


def test_pdf_writer_handles_empty_and_long_text(tmp_path):
    p1 = write_pdf("", tmp_path / "a.pdf")
    assert p1.read_bytes()[:5] == b"%PDF-"
    long_text = "\n".join(f"line {i} " + "x" * 200 for i in range(200))
    p2 = write_pdf(long_text, tmp_path / "b.pdf")
    assert b"%%EOF" in p2.read_bytes()
