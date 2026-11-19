"""Generate the per-tool guides from catalog.yaml (the single source of truth).

Writes:
  adapters/claude-code/CLAUDE.md
  adapters/kiro/steering/eu-ai-compliance.md

Both are plain-language feed-forward guides: what is forbidden (Art. 5 -> BLOCK),
what is high-risk (Annex III -> WARN + artefacts), the secrets rule, and the
note that the hook (not the guide) decides. Deterministic: a committed test
asserts the outputs are up to date.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aca.catalog.loader import load_catalog  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
_CLAUDE = _ROOT / "adapters" / "claude-code" / "CLAUDE.md"
_KIRO = _ROOT / "adapters" / "kiro" / "steering" / "eu-ai-compliance.md"
_CURSOR = _ROOT / "adapters" / "cursor" / "rules" / "eu-ai-compliance.mdc"
_COPILOT = _ROOT / "adapters" / "copilot" / "copilot-instructions.md"
_CODEX = _ROOT / "adapters" / "codex" / "AGENTS.md"

# For tools without a deterministic pre-tool hook, the guide is advisory and the
# enforcement happens in CI + the MCP compliance_check tool. State that plainly.
_GUIDANCE_ONLY = (
    "This tool does not run the compliance hook as a blocking pre-tool check, so "
    "these rules are guidance for the model, not enforcement. The real gates are "
    "the CI check (guardrails-ci) on every pull request and, where wired, the MCP "
    "`compliance_check` tool. Treat a BLOCK item as something the PR will fail on."
)

_INTRO = (
    "Halvaro Payments GmbH (fictional client of Northwind Advisory) builds "
    "software with AI coding tools under the EU AI Act, GDPR and ISO/IEC 42001. "
    "These rules tell you what to avoid and what to declare. They are guidance: "
    "the compliance hook makes the actual decision on every prompt and tool call, "
    "and the CI and deploy gates enforce it. Synthetic data only; not legal "
    "advice and not a conformity claim."
)


def _by_decision(checks: list[dict], dec: str) -> list[dict]:
    return [c for c in checks if c.get("dec") == dec]


def _bullet(c: dict) -> str:
    return f"- **{c['id']}** — {c['title']} ({c['src']})."


def _guide_body(checks: list[dict]) -> list[str]:
    block = _by_decision(checks, "BLOCK")
    # Annex III high-risk (WARN) rows have ids starting AIA-A3-.
    annex = [c for c in checks if c.get("dec") == "WARN" and c["id"].startswith("AIA-A3-")]

    lines: list[str] = []
    lines.append("## Never build these (refused — EU AI Act Art. 5 and hard security rules)")
    lines.append("")
    lines.append("If a request amounts to one of these, the hook returns BLOCK and the tool "
                 "refuses. This holds even when the wording avoids the obvious terms "
                 "(for example, social scoring described only as joining behaviour data "
                 "into a score and acting on it).")
    lines.append("")
    for c in block:
        lines.append(_bullet(c))
    lines.append("")
    lines.append("## High-risk — allowed, but it must be declared and gated (EU AI Act Annex III)")
    lines.append("")
    lines.append("If you build one of these, keep working, but the hook returns WARN and lists "
                 "the artefacts the law requires (risk assessment, DPIA, human-oversight plan, "
                 "evaluation report, worker information, and a FRIA for credit or insurance). "
                 "Declare the feature in `use-case.yaml`; the deploy gate blocks production until "
                 "those artefacts exist and two different people have approved them.")
    lines.append("")
    for c in annex:
        lines.append(_bullet(c))
    lines.append("")
    lines.append("## Secrets")
    lines.append("")
    lines.append("Never put a key, token or password in code, config, prompts or rules files. "
                 "The hook scans writes and shell commands and returns BLOCK for a secret; use a "
                 "vault or environment variable instead.")
    lines.append("")
    lines.append("## How a decision is made")
    lines.append("")
    lines.append("- **BLOCK** — refused; the message names the rule.")
    lines.append("- **ASK** — pauses for a human decision (ambiguous, or a solely-automated "
                 "decision about a person).")
    lines.append("- **WARN** — continue; obligations are shown and required before deployment.")
    lines.append("- **ALLOW** — nothing to do.")
    lines.append("")
    lines.append("The hook decides; this guide only explains. If the policy service is "
                 "unreachable, the hook fails safe to ASK, and a secret write is still blocked.")
    return lines


def render_claude(checks: list[dict]) -> str:
    lines = [
        "# EU AI compliance — guide for AI coding tools (Claude Code)",
        "",
        "<!-- Generated from policy/catalog/catalog.yaml by adapters/generate_guides.py. Do not edit by hand. -->",
        "",
        _INTRO,
        "",
    ]
    lines += _guide_body(checks)
    return "\n".join(lines) + "\n"


def render_kiro(checks: list[dict]) -> str:
    lines = [
        "# EU AI compliance (steering)",
        "",
        "<!-- Generated from policy/catalog/catalog.yaml by adapters/generate_guides.py. Do not edit by hand. -->",
        "",
        _INTRO,
        "",
    ]
    lines += _guide_body(checks)
    return "\n".join(lines) + "\n"


def render_cursor(checks: list[dict]) -> str:
    # Cursor .mdc rules carry YAML frontmatter; alwaysApply keeps them in context.
    lines = [
        "---",
        "description: EU AI compliance rules (generated from the policy catalog)",
        "alwaysApply: true",
        "---",
        "",
        "# EU AI compliance (Cursor rules)",
        "",
        "<!-- Generated from policy/catalog/catalog.yaml by adapters/generate_guides.py. Do not edit by hand. -->",
        "",
        _INTRO,
        "",
        "Cursor also runs the compliance hook (`guardrails-hook cursor ...`) as a "
        "pre-tool check where configured; see adapters/cursor/README.md.",
        "",
    ]
    lines += _guide_body(checks)
    return "\n".join(lines) + "\n"


def render_copilot(checks: list[dict]) -> str:
    lines = [
        "# EU AI compliance — GitHub Copilot instructions",
        "",
        "<!-- Generated from policy/catalog/catalog.yaml by adapters/generate_guides.py. Do not edit by hand. -->",
        "",
        _INTRO,
        "",
        _GUIDANCE_ONLY,
        "",
    ]
    lines += _guide_body(checks)
    return "\n".join(lines) + "\n"


def render_codex(checks: list[dict]) -> str:
    lines = [
        "# AGENTS.md — EU AI compliance (Codex / agents)",
        "",
        "<!-- Generated from policy/catalog/catalog.yaml by adapters/generate_guides.py. Do not edit by hand. -->",
        "",
        _INTRO,
        "",
        _GUIDANCE_ONLY,
        "",
    ]
    lines += _guide_body(checks)
    return "\n".join(lines) + "\n"


def main() -> int:
    checks = load_catalog()["checks"]
    outputs = {
        _CLAUDE: render_claude(checks),
        _KIRO: render_kiro(checks),
        _CURSOR: render_cursor(checks),
        _COPILOT: render_copilot(checks),
        _CODEX: render_codex(checks),
    }
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print("wrote: " + ", ".join(str(p.relative_to(_ROOT)) for p in outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
