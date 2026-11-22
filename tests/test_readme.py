"""Phase 9 — README structure check (R16.1, R16.2, R16.4)."""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
README = (REPO / "README.md").read_text(encoding="utf-8")


def test_names_semantic_guard_as_core():
    assert "Core component: Semantic Guard" in README


def test_has_skimmable_sections():
    # v2 README headings (renamed from v1: "Problem" -> "The story in one paragraph",
    # added a per-phase "Status" table).
    for heading in ("## The story in one paragraph", "## Architecture", "## Status",
                    "## Semantic Guard", "## How to run", "## Results", "## Limitations"):
        assert heading in README, f"missing section: {heading}"


def test_has_disclaimer_and_synthetic_data():
    assert "Synthetic data only" in README
    assert "not a conformity claim" in README.lower()


def test_results_have_provenance_or_to_be_measured():
    # The detection numbers are the frozen operating point from the owner's real
    # run; the results prose names that provenance (model + tuning-only, no run
    # timestamps/SHAs/paths after the freeze), and the table still carries TO BE
    # MEASURED for the unmeasured vendor/stage-2-3 paths.
    assert "frozen operating point" in README
    assert "TO BE MEASURED" in README


def test_no_employer_branding():
    lowered = README.lower()
    for banned in ("telekom", "magenta", "deutsche telekom"):
        assert banned not in lowered


def test_references_architecture_diagram_path():
    # v2 hero image is the v2 architecture diagram under docs/v2/img/.
    assert "docs/v2/img/architecture-v2.png" in README
