"""Fix #4 — the single combined calibration command.

Element margins are calibrated first, then the ASK thresholds on top of that
final element regime, with the combined benign-review cap (ASK + four-eyes).
Tuning only; never reads held-out. Uses the offline hashed embedder.

The combined calibration is expensive (it rebuilds adapters while sweeping), so
it is computed ONCE in a module-scoped fixture and shared across assertions.
"""

import json
from pathlib import Path

import pytest

from aca.eval import calibrate_ask, calibrate_elements
from aca.eval.calibrate import calibrate, write_report


@pytest.fixture(scope="module")
def report():
    return calibrate(cap=0.15)


def test_combined_produces_both_sections(report):
    assert "element_margins" in report and "ask_thresholds" in report
    assert report["benign_review_cap"] == 0.15
    assert "element margins calibrated first" in report["order"]
    em = set(report["element_margins"]["concepts"])
    ak = set(report["ask_thresholds"]["concepts"])
    assert em == ak and len(em) == 13


def test_combined_ask_cap_is_on_ask_plus_four_eyes(report):
    assert report["ask_thresholds"]["cap_measures"].startswith("benign routed to ASK + four-eyes")


def test_combined_writes_both_files(report, tmp_path):
    margins = tmp_path / "element_margins.json"
    thresholds = tmp_path / "thresholds.json"
    src = Path(__file__).resolve().parents[1] / "policy" / "data" / "thresholds.json"
    thresholds.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    calibrate_elements.write_margins(report["element_margins"], margins_path=margins)
    calibrate_ask.write_thresholds(report["ask_thresholds"], thresholds_path=thresholds)

    m = json.loads(margins.read_text())
    assert "concepts" in m and "default_margin" in m
    for cid, info in m["concepts"].items():
        for el, v in info.items():
            assert v["margin"] is None or v["margin"] >= m["default_margin"]


def test_combined_report_writes_to_results(report, tmp_path):
    p = write_report(report, results_dir=tmp_path)
    assert p.exists()
    assert json.loads(p.read_text())["schema"] == "calibration/v1"


def test_combined_never_reads_heldout(monkeypatch):
    seen: list[str] = []
    for mod in (calibrate_ask, calibrate_elements):
        real = mod.load_yaml
        def _spy(path, _real=real):
            seen.append(str(path))
            return _real(path)
        monkeypatch.setattr(mod, "load_yaml", _spy)
    calibrate(cap=0.15)
    assert seen
    assert not any("heldout" in s.lower() or "held_out" in s.lower() for s in seen)


def test_combined_filesystem_audit_touches_no_heldout_path(monkeypatch):
    # Fix #5: hook the low-level filesystem entry points too (Path.read_text /
    # read_bytes, os.open, builtins.open), not just load_yaml, and assert no
    # held-out path is opened anywhere during a full combined calibration.
    import builtins
    import os
    from pathlib import Path

    seen: list[str] = []

    def _bad(p: str) -> bool:
        low = str(p).lower()
        return "heldout" in low or "held_out" in low

    real_read_text = Path.read_text
    real_read_bytes = Path.read_bytes
    real_open = builtins.open
    real_os_open = os.open

    def _rt(self, *a, **k):
        seen.append(str(self))
        return real_read_text(self, *a, **k)

    def _rb(self, *a, **k):
        seen.append(str(self))
        return real_read_bytes(self, *a, **k)

    def _op(file, *a, **k):
        seen.append(str(file))
        return real_open(file, *a, **k)

    def _oso(path, *a, **k):
        seen.append(str(path))
        return real_os_open(path, *a, **k)

    monkeypatch.setattr(Path, "read_text", _rt)
    monkeypatch.setattr(Path, "read_bytes", _rb)
    monkeypatch.setattr(builtins, "open", _op)
    monkeypatch.setattr(os, "open", _oso)

    calibrate(cap=0.15)

    offenders = [s for s in seen if _bad(s)]
    assert not offenders, f"calibration touched held-out paths: {offenders[:5]}"
