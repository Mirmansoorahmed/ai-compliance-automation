"""Phase 0 — catalog.yaml loads, validates, and is up to date."""

import subprocess
import sys
from pathlib import Path

from aca.catalog.loader import load_catalog, catalog_path
from aca.catalog.validate import VALID_DECISIONS, validate_catalog

REPO = Path(__file__).resolve().parents[1]


def test_catalog_loads_120_checks():
    data = load_catalog()
    assert data["version"]
    assert len(data["checks"]) == 120


def test_catalog_validates_clean():
    errors = validate_catalog()
    assert errors == [], errors


def test_ids_are_unique():
    checks = load_catalog()["checks"]
    ids = [c["id"] for c in checks]
    assert len(set(ids)) == len(ids)


def test_every_decision_is_valid():
    checks = load_catalog()["checks"]
    for c in checks:
        assert c["dec"] in VALID_DECISIONS, c["id"]


def test_every_check_has_source_and_enforcement_points():
    checks = load_catalog()["checks"]
    for c in checks:
        assert c["src"].strip(), f"{c['id']} missing src"
        assert c["ep"].strip(), f"{c['id']} missing ep"


def test_decision_counts_match_design():
    from collections import Counter

    counts = Counter(c["dec"] for c in load_catalog()["checks"])
    assert counts["BLOCK"] == 20
    assert counts["ASK"] == 24
    assert counts["WARN"] == 56
    assert counts["ALLOW"] == 20


def test_social_scoring_is_block_and_fraud_pattern_present():
    checks = {c["id"]: c for c in load_catalog()["checks"]}
    assert checks["AIA-5-1-c"]["dec"] == "BLOCK"
    assert checks["AIA-A3-4a"]["dec"] == "WARN"
    assert checks["AIA-A3-5b"]["dec"] == "WARN"
    assert checks["SEC-SECRETS"]["dec"] == "BLOCK"


def test_committed_catalog_is_up_to_date():
    # Re-running the generator must reproduce the committed catalog byte-for-byte.
    gen = REPO / "policy" / "catalog" / "generate_catalog.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location("generate_catalog", gen)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    expected = mod.render_yaml()
    actual = catalog_path().read_text(encoding="utf-8")
    assert actual == expected, "catalog.yaml is stale; run python3 policy/catalog/generate_catalog.py"
