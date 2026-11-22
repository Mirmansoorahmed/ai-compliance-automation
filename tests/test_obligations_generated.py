"""Phase 1 — generated OPA data (catalog.json, obligations.json) is up to date."""

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "policy" / "data"


def _gen_module():
    gen = REPO / "policy" / "catalog" / "generate_obligations.py"
    spec = importlib.util.spec_from_file_location("generate_obligations", gen)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_catalog_json_up_to_date():
    mod = _gen_module()
    assert (DATA / "catalog.json").read_text(encoding="utf-8") == mod.render_catalog_json(), \
        "policy/data/catalog.json is stale; run python3 policy/catalog/generate_obligations.py"


def test_obligations_json_up_to_date():
    mod = _gen_module()
    assert (DATA / "obligations.json").read_text(encoding="utf-8") == mod.render_obligations_json(), \
        "policy/data/obligations.json is stale; run python3 policy/catalog/generate_obligations.py"


def test_obligations_match_decisions_for_key_checks():
    obl = json.loads((DATA / "obligations.json").read_text())["obligations"]
    # CV screening obligations include worker_information; credit scoring includes fria.
    assert "worker_information" in obl["AIA-A3-4a"]
    assert "fria" in obl["AIA-A3-5b"]
    # FRIA must NOT leak onto GDPR-35 (whose art only "feeds FRIA").
    assert "fria" not in obl.get("GDPR-35", [])


def test_fria_only_on_expected_checks():
    obl = json.loads((DATA / "obligations.json").read_text())["obligations"]
    fria_checks = {cid for cid, keys in obl.items() if "fria" in keys}
    assert fria_checks == {"AIA-27", "AIA-A3-5a", "AIA-A3-5b", "AIA-A3-5c", "AIA-A3-6a-e", "AIA-A3-7a-d"}
