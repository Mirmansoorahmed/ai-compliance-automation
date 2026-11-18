"""Phase 8 — coverage report tests (R11.3, R11.4)."""

from pathlib import Path

from aca.eval.coverage import compute_coverage

REPO = Path(__file__).resolve().parents[1]


def test_real_register_coverage_is_fully_mapped():
    report = compute_coverage(REPO / "requirements", floor_file=REPO / "eval" / "coverage_floor.json")
    assert report.total == 11
    assert report.pct_mapped == 100.0
    assert report.passes_floor
    # Mode shares reported (auto/human/hybrid).
    assert report.by_mode == {"auto": 4, "human": 1, "hybrid": 6}


def test_coverage_fails_below_floor_on_broken_fixture(tmp_path):
    req = tmp_path / "requirements"
    req.mkdir()
    # Two requirements, one retired -> mapped share 50% < floor 90%.
    (req / "a.yaml").write_text(
        "id: REQ-A\nsource: EU AI Act\ncitation: Art. 5\ntitle: t\nmode: auto\n"
        "owner: o\nstatus: active\n",
        encoding="utf-8",
    )
    (req / "b.yaml").write_text(
        "id: REQ-B\nsource: EU AI Act\ncitation: Art. 9\ntitle: t\nmode: human\n"
        "owner: o\nstatus: retired\n",
        encoding="utf-8",
    )
    floor = tmp_path / "floor.json"
    floor.write_text('{"pct_mapped_floor": 90.0}', encoding="utf-8")
    report = compute_coverage(req, floor_file=floor)
    assert report.pct_mapped == 50.0
    assert report.passes_floor is False


def test_floor_is_labelled_target_not_result():
    report = compute_coverage(REPO / "requirements", floor_file=REPO / "eval" / "coverage_floor.json")
    assert "TARGET" in report.to_dict()["floor_note"]
