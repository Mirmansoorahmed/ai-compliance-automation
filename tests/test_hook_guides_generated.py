"""Phase 2 — the generated tool guides are up to date with catalog.yaml.

adapters/generate_guides.py renders CLAUDE.md and the Kiro steering file from
policy/catalog/catalog.yaml (the single source of truth). This test regenerates
in memory and asserts the committed files match, so the guides can never drift
from the catalog. No network, no model.
"""

from pathlib import Path

from aca.catalog.loader import load_catalog

import importlib.util

_ROOT = Path(__file__).resolve().parents[1]
_GEN = _ROOT / "adapters" / "generate_guides.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_guides", _GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_claude_guide_is_up_to_date():
    gen = _load_generator()
    checks = load_catalog()["checks"]
    expected = gen.render_claude(checks)
    actual = (_ROOT / "adapters" / "claude-code" / "CLAUDE.md").read_text(encoding="utf-8")
    assert actual == expected, "CLAUDE.md is stale — run: python3 adapters/generate_guides.py"


def test_kiro_steering_is_up_to_date():
    gen = _load_generator()
    checks = load_catalog()["checks"]
    expected = gen.render_kiro(checks)
    actual = (_ROOT / "adapters" / "kiro" / "steering" / "eu-ai-compliance.md").read_text(encoding="utf-8")
    assert actual == expected, "eu-ai-compliance.md is stale — run: python3 adapters/generate_guides.py"


def test_cursor_rules_is_up_to_date():
    gen = _load_generator()
    checks = load_catalog()["checks"]
    expected = gen.render_cursor(checks)
    actual = (_ROOT / "adapters" / "cursor" / "rules" / "eu-ai-compliance.mdc").read_text(encoding="utf-8")
    assert actual == expected, "cursor rules stale — run: python3 adapters/generate_guides.py"


def test_copilot_instructions_is_up_to_date():
    gen = _load_generator()
    checks = load_catalog()["checks"]
    expected = gen.render_copilot(checks)
    actual = (_ROOT / "adapters" / "copilot" / "copilot-instructions.md").read_text(encoding="utf-8")
    assert actual == expected, "copilot instructions stale — run: python3 adapters/generate_guides.py"


def test_codex_agents_is_up_to_date():
    gen = _load_generator()
    checks = load_catalog()["checks"]
    expected = gen.render_codex(checks)
    actual = (_ROOT / "adapters" / "codex" / "AGENTS.md").read_text(encoding="utf-8")
    assert actual == expected, "codex AGENTS.md stale — run: python3 adapters/generate_guides.py"


def test_guides_mention_core_rules():
    for name in ("adapters/claude-code/CLAUDE.md",
                 "adapters/kiro/steering/eu-ai-compliance.md"):
        text = (_ROOT / name).read_text(encoding="utf-8")
        assert "Art. 5" in text
        assert "Annex III" in text
        assert "Halvaro Payments GmbH" in text
        assert "Northwind Advisory" in text
