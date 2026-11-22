"""Build the human-readable message and obligation text from a decision dict.

Shared by the Claude Code and Kiro renderers so the wording is consistent.
Never invents numbers; only restates the checks, articles and obligations the
policy service returned.
"""

from __future__ import annotations

CONCERN_CHANNEL = "Raise a concern or request a review: #ai-compliance (ISO 42001 A.3.3)."


def _refs(decision: dict) -> str:
    parts = []
    for r in decision.get("reasons", []):
        cid = r.get("check_id")
        src = r.get("source", "")
        if cid:
            parts.append(f"{cid} ({src})" if src else cid)
    return "; ".join(parts)


def obligations_lines(decision: dict) -> list[str]:
    lines = []
    obligations = decision.get("obligations") or []
    missing = set(decision.get("missing_artefacts") or [])
    if obligations:
        lines.append("Required before deployment (write these into use-case.yaml):")
        for o in obligations:
            mark = "missing" if o in missing else "present"
            lines.append(f"  - {o} ({mark})")
    return lines


def summary(decision: dict) -> str:
    """One-line human summary of the decision."""
    d = decision.get("decision", "ASK")
    refs = _refs(decision)
    if d == "BLOCK":
        base = "Blocked: this is a prohibited or hard-blocked practice."
    elif d == "ASK":
        base = "Needs a human decision before proceeding."
    elif d == "WARN":
        base = "Allowed to continue — this is a high-risk use; obligations are required before deployment."
    else:
        base = "Allowed."
    if refs:
        base += f" Rule(s): {refs}."
    return base


def full_message(decision: dict, *, include_obligations: bool = True) -> str:
    """Multi-line message: summary + obligations + concern channel."""
    lines = [summary(decision)]
    if include_obligations:
        lines += obligations_lines(decision)
    if decision.get("decision") in ("BLOCK", "ASK", "WARN"):
        lines.append(CONCERN_CHANNEL)
    return "\n".join(lines)
