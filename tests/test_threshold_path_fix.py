"""Threshold-path + write/reload fixes after the real-model run.

Fix 1: the adapter must resolve policy/data via the shared helper and load the
committed thresholds.json (non-empty) from the real repo layout — the old
Path(...).parents[3] pointed at a non-existent src/policy/data and silently
disabled the ASK tier.

Fix 2: the ASK calibrator must write the exact threshold it evaluated (incl. the
grid-max "no ASK" value), so reload -> score reproduces the calibrator's
reported benign/recall numbers.

Fix 4: the eval JSON records the thresholds path, sha256 and active-ASK count.
"""

import json
from pathlib import Path

import pytest

from aca.guard.adapters.local_embeddings import (
    _load_ask_thresholds,
    ask_thresholds_status,
)
from aca.paths import policy_data_dir, thresholds_path

_REPO = Path(__file__).resolve().parents[1]


# --- Fix 1 ---------------------------------------------------------------------

def test_shared_policy_data_dir_points_at_real_repo_layout():
    d = policy_data_dir()
    assert d == _REPO / "policy" / "data", d
    assert (d / "thresholds.json").is_file()
    assert (d / "element_margins.json").is_file()
    # Not the broken src/policy/data path.
    assert "src" not in d.parts[-3:]


def test_adapter_resolves_and_reads_the_committed_thresholds_file():
    # The committed thresholds.json is found at the real repo path and is a
    # non-empty tier-threshold file (low/high/min_elements per concept). Whether
    # ask_threshold is present depends on calibration — the committed default
    # ships with the similarity ASK tier OFF (no ask_threshold) until the owner
    # calibrates, which is a valid, logged state (not the old broken silent {}).
    data = json.loads(thresholds_path().read_text(encoding="utf-8"))["thresholds"]
    assert data, "committed thresholds.json tier block is empty"
    assert "AIA-5-1-c" in data and "low" in data["AIA-5-1-c"]
    # _load_ask_thresholds resolves without error; every value (if any) is sane.
    for cid, v in _load_ask_thresholds().items():
        assert isinstance(v, float) and 0.0 <= v <= 1.0


def test_ask_thresholds_status_reports_real_path():
    st = ask_thresholds_status()
    assert st["exists"] is True
    assert st["path"].endswith("policy/data/thresholds.json")
    assert "/src/policy/" not in st["path"]  # not the old broken path
    # ask_thresholds_loaded reflects whether any ask_threshold is set; both
    # states are valid, but the count must equal the loaded map size.
    assert st["n_active_ask_thresholds"] == len(_load_ask_thresholds())
    assert st["ask_thresholds_loaded"] == bool(_load_ask_thresholds())


def test_policy_data_dir_env_override(monkeypatch, tmp_path):
    from aca import paths
    monkeypatch.setenv(paths.POLICY_DATA_DIR_ENV, str(tmp_path))
    assert paths.policy_data_dir() == tmp_path
    assert paths.thresholds_path() == tmp_path / "thresholds.json"


# --- Fix 2 ---------------------------------------------------------------------

def test_calibrate_write_reload_reproduces_reported_numbers(tmp_path):
    # calibrate -> write thresholds -> reload through the adapter -> re-score the
    # tuning sets; the achieved benign/recall must match the calibrator report.
    from aca.eval import calibrate_ask, calibrate_elements
    from aca.eval.calibrate_ask import (
        _case_cache,
        _load_tuning_cases,
        _review_frac,
    )

    # Final element regime first (so ASK calibrates on top of it).
    elem = calibrate_elements.calibrate()
    element_margins = {
        "default_margin": elem["default_margin"],
        "concepts": {c: {k: v for k, v in i.items() if k != "_meta"} for c, i in elem["concepts"].items()},
    }
    report = calibrate_ask.calibrate(benign_review_cap=0.15, element_margins=element_margins)

    # Write thresholds to a temp copy of the committed file.
    dst = tmp_path / "thresholds.json"
    dst.write_text((_REPO / "policy" / "data" / "thresholds.json").read_text(), encoding="utf-8")
    calibrate_ask.write_thresholds(report, thresholds_path=dst)

    # Reload the written ask_thresholds and re-score through the SAME tier logic
    # the calibrator used (cached facts + _tier_for_case).
    written = json.loads(dst.read_text())["thresholds"]
    reloaded = {c: th["ask_threshold"] for c, th in written.items() if "ask_threshold" in th}

    all_cases = _load_tuning_cases()
    benign = [c for c in all_cases if c.get("category") in ("benign", "ambiguous")]
    attacks = [c for c in all_cases if c.get("expect_pattern")]
    from aca.guard.embeddings import build_embedder
    emb = build_embedder(allow_hashed_fallback=True, dim=256)
    clist = list(report["concepts"].keys())
    bcache = _case_cache(emb, clist, benign, element_margins)
    acache = _case_cache(emb, clist, attacks, element_margins)

    benign_rate = round(_review_frac(bcache, reloaded), 4)
    recall_rate = round(_review_frac(acache, reloaded), 4)

    assert benign_rate == report["achieved_benign_review_rate"], (
        f"reloaded benign {benign_rate} != reported {report['achieved_benign_review_rate']}")
    assert recall_rate == report["achieved_review_recall"], (
        f"reloaded recall {recall_rate} != reported {report['achieved_review_recall']}")


def test_written_thresholds_match_evaluated_values(tmp_path):
    # Every concept's written ask_threshold equals the exact value the
    # calibrator evaluated (no stale placeholder like 0.5 for a no-ASK concept).
    from aca.eval import calibrate_ask, calibrate_elements
    elem = calibrate_elements.calibrate()
    element_margins = {
        "default_margin": elem["default_margin"],
        "concepts": {c: {k: v for k, v in i.items() if k != "_meta"} for c, i in elem["concepts"].items()},
    }
    report = calibrate_ask.calibrate(benign_review_cap=0.15, element_margins=element_margins)
    dst = tmp_path / "thresholds.json"
    dst.write_text((_REPO / "policy" / "data" / "thresholds.json").read_text(), encoding="utf-8")
    calibrate_ask.write_thresholds(report, thresholds_path=dst)
    written = json.loads(dst.read_text())["thresholds"]
    for cid, info in report["concepts"].items():
        if cid in written and "ask_threshold" in written[cid]:
            assert written[cid]["ask_threshold"] == info["chosen_ask_threshold"]
