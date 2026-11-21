"""Phase A — tests for the ASK-threshold calibrator.

Uses the offline hashed embedder. Checks that calibration sweeps the tuning set,
respects the benign-ASK cap, writes thresholds only for chosen concepts, and —
critically — never reads any held-out directory.
"""

from pathlib import Path

import pytest

from aca.eval import calibrate_ask
from aca.eval.calibrate_ask import (
    HeldOutAccessError,
    _assert_not_heldout,
    calibrate,
    write_thresholds,
)


def test_calibrate_runs_on_tuning_and_covers_13_concepts():
    report = calibrate(benign_ask_cap=0.15)
    assert len(report["concepts"]) == 13
    for cid, info in report["concepts"].items():
        # Every concept has a sweep table; chosen may be None if the cap can't
        # be met, but then the note explains it.
        assert info["sweep"], f"{cid} has no sweep rows"
        if info["chosen_ask_threshold"] is None:
            assert info["note"]


def test_chosen_threshold_respects_benign_review_cap():
    cap = 0.15
    report = calibrate(benign_review_cap=cap)
    for cid, info in report["concepts"].items():
        chosen = info["chosen_ask_threshold"]
        if chosen is None:
            continue
        row = next(r for r in info["sweep"] if r["threshold"] == chosen)
        # The cap is on the COMBINED benign review rate (ASK + four-eyes).
        assert row["benign_review_rate"] <= cap, f"{cid}: benign review over cap at chosen threshold"


def test_chosen_is_lowest_threshold_meeting_cap():
    cap = 0.15
    report = calibrate(benign_review_cap=cap)
    for cid, info in report["concepts"].items():
        chosen = info["chosen_ask_threshold"]
        if chosen is None:
            continue
        # No lower threshold in the grid should also meet the cap.
        for r in info["sweep"]:
            if r["threshold"] < chosen:
                assert r["benign_review_rate"] > cap, (
                    f"{cid}: a lower threshold {r['threshold']} also met the cap")


def test_write_thresholds_only_sets_ask_threshold(tmp_path):
    # Copy the real thresholds file so we don't mutate the repo's.
    import json
    src = Path(__file__).resolve().parents[1] / "policy" / "data" / "thresholds.json"
    dst = tmp_path / "thresholds.json"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    before = json.loads(dst.read_text())

    report = calibrate(benign_review_cap=0.15)
    write_thresholds(report, thresholds_path=dst)
    after = json.loads(dst.read_text())

    # low/high/min_elements unchanged; only ask_threshold may change.
    for cid, th in before["thresholds"].items():
        for key in ("low", "high", "min_elements"):
            if key in th:
                assert after["thresholds"][cid][key] == th[key]


def test_assert_not_heldout_blocks_heldout_paths():
    for bad in ("eval/heldout", "eval/heldout_v2", "/x/held_out/cases"):
        with pytest.raises(HeldOutAccessError):
            _assert_not_heldout(Path(bad))
    # A tuning path is fine.
    _assert_not_heldout(Path("eval/tuning_v2"))
    _assert_not_heldout(Path("eval/cases"))


def test_calibrator_tuning_dirs_exclude_heldout():
    # The module's configured tuning dirs must not include any held-out dir.
    for d in calibrate_ask._TUNING_DIRS:
        assert "heldout" not in str(d).lower()
        assert "held_out" not in str(d).lower()


def test_calibrator_never_opens_heldout(monkeypatch):
    # Instrument load_yaml to record every path the calibrator reads, then assert
    # none is under a held-out directory.
    seen: list[str] = []
    real = calibrate_ask.load_yaml

    def _spy(path):
        seen.append(str(path))
        return real(path)

    monkeypatch.setattr(calibrate_ask, "load_yaml", _spy)
    calibrate(benign_ask_cap=0.15)
    assert seen, "calibrator read no cases"
    assert not any("heldout" in s.lower() or "held_out" in s.lower() for s in seen)
