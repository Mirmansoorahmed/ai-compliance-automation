"""Render the evidence pack v2 as an auditor-readable narrative.

The output is a plain-language trace of one use case from prompt to production,
the ISO 42001 / EU AI Act mapping table, and the approval + break-glass records.
A guard enforces the "no code, no file paths, no hashes in the PDF body" rule:
``assert_clean`` rejects text that looks like a path, a long hex hash, or a code
fence, so a regression cannot leak those into the pack.
"""

from __future__ import annotations

import re

from aca.evidence_pack.collect import EvidenceTrace, mapping_table

DISCLAIMER = (
    "Lab / portfolio project. Synthetic data only (fictional firms Northwind "
    "Advisory and Halvaro Payments GmbH). Mappings to the EU AI Act, GDPR and "
    "ISO/IEC 42001 are illustrative and in our own words; not legal advice and "
    "not a conformity claim."
)

# Patterns that must not appear in the PDF body.
_PATH_RE = re.compile(r"(?:(?<=\s)|^)(?:\.{0,2}/)?(?:[\w.-]+/){2,}[\w.-]+")
_HASH_RE = re.compile(r"\b[0-9a-f]{12,}\b", re.IGNORECASE)
_CODEFENCE_RE = re.compile(r"```")


class EvidencePackError(RuntimeError):
    pass


def assert_clean(text: str) -> None:
    """Raise if the body contains a file path, a long hex hash, or a code fence."""
    if _CODEFENCE_RE.search(text):
        raise EvidencePackError("evidence pack body must not contain code blocks")
    if _HASH_RE.search(text):
        raise EvidencePackError("evidence pack body must not contain hashes")
    if _PATH_RE.search(text):
        raise EvidencePackError("evidence pack body must not contain file paths")


_POINT_LABEL = {
    "editor": "Editor (AI coding tool)",
    "ci": "Pull request (CI gate)",
    "deploy": "Deployment (deploy gate)",
    "runtime": "Runtime (Agent Trust Gateway)",
}


def render_text(trace: EvidenceTrace) -> str:
    lines: list[str] = []
    lines.append("AI Semantic Guardrails EU — Evidence Pack (v2)")
    lines.append("Auditor view: one use case from prompt to production.")
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")
    lines.append("=" * 72)
    lines.append(f"Use case: {trace.use_case_title}")
    lines.append("=" * 72)
    lines.append("")

    lines.append("1. Decision trace (in order)")
    lines.append("-" * 72)
    for i, p in enumerate(trace.points, 1):
        rules = (" [" + ", ".join(p.rules) + "]") if p.rules else ""
        lines.append(f"{i}. {_POINT_LABEL.get(p.point, p.point)} — {p.stage}")
        lines.append(f"   Decision: {p.decision}{rules}")
        lines.append(f"   {p.summary}")
        lines.append("")

    lines.append("2. Required artefacts (obligations) and approvals")
    lines.append("-" * 72)
    lines.append("Required artefacts for this high-risk use case:")
    for o in trace.obligations:
        lines.append(f"  - {o.replace('_', ' ')}")
    lines.append("")
    lines.append("Approvals recorded (two distinct people):")
    for a in trace.approvals:
        lines.append(f"  - {a['approver_role']} approved: {a['artefact']}")
    bg = trace.break_glass or {}
    lines.append("")
    lines.append(f"Break-glass: {bg.get('note', 'none recorded')}")
    lines.append("")

    lines.append("3. ISO/IEC 42001 and EU AI Act mapping")
    lines.append("-" * 72)
    for row in mapping_table():
        lines.append(f"- {row['control']}")
        lines.append(f"  EU AI Act: {row['act']}")
        lines.append(f"  Enforced at: {row['enforced_at']}")
    lines.append("")
    lines.append(DISCLAIMER)

    text = "\n".join(lines)
    assert_clean(text)
    return text
