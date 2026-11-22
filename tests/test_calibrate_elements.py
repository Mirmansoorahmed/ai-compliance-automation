"""Phase C — tests for the element-margin calibrator (hashed embedder)."""

from pathlib import Path

import pytest

from aca.eval import calibrate_elements
from aca.eval.calibrate_ask import HeldOutAccessError
from aca.eval.calibrate_elements import calibrate, write_margins


def test_calibrate_covers_all_concepts_and_hits_zero_false_full_match_on_tuning():
    report = calibrate()
    assert report["concepts"]
    for cid, info in report["concepts"].items():
        meta = info["_meta"]
        # Either the tuning cross-concept false-full-match rate is 0, or the
        # concept's full match was disabled — never a non-zero false full match.
        assert meta["false_full_match_rate_tuning"] == 0.0 or meta["full_match_disabled"]


def test_margins_are_strictly_positive_or_null():
    # Fix #1: a chosen margin is never 0.0; it is >= the floor or null (disabled).
    report = calibrate()
    floor = report["floor"]
    for cid, info in report["concepts"].items():
        for element, m in info.items():
            if element == "_meta":
                continue
            margin = m["margin"]
            assert margin is None or margin >= floor, f"{cid}:{element} margin {margin} below floor"


def test_stability_warnings_present_for_small_or_zero_recall_concepts():
    # Fix #5: concepts with 0 positive full matches carry a warning.
    report = calibrate()
    for cid, info in report["concepts"].items():
        meta = info["_meta"]
        if meta["pos_full_match_count"] == 0 and not meta["full_match_disabled"]:
            assert meta["warnings"], f"{cid} should warn about 0 positive full matches"


def test_calibrator_never_reads_heldout(monkeypatch):
    seen: list[str] = []
    real = calibrate_elements.load_yaml

    def _spy(path):
        seen.append(str(path))
        return real(path)

    monkeypatch.setattr(calibrate_elements, "load_yaml", _spy)
    calibrate()
    assert seen
    assert not any("heldout" in s.lower() or "held_out" in s.lower() for s in seen)


def test_tuning_dirs_exclude_heldout():
    for d in calibrate_elements._TUNING_DIRS:
        assert "heldout" not in str(d).lower()


def test_write_margins_roundtrips(tmp_path):
    import json
    report = calibrate()
    out = tmp_path / "element_margins.json"
    write_margins(report, margins_path=out)
    data = json.loads(out.read_text())
    assert "concepts" in data and "default_margin" in data
    # _meta is not written into the margins file (only margins).
    for cid, info in data["concepts"].items():
        assert "_meta" not in info
