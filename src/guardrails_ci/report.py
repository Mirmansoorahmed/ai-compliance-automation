"""Render the PR-comment-ready ci-report.md from a CiResult.

Sections:
  - a one-line decision badge (BLOCK / ASK / WARN / ALLOW) + what it means;
  - the rules that fired, each with its legal source (from the catalog);
  - a pending-obligations checklist for a WARN use case (present / missing,
    from use-case.yaml artefact paths), using the catalog's real count;
  - the status of the optional external scanners (gitleaks, Semgrep);
  - the changed files considered.

Plain language, no invented numbers. The obligation count is whatever the
catalog yields for the declared use case.
"""

from __future__ import annotations

from guardrails_ci.engine import CiResult
from guardrails_ci.tools import ToolResult

_MEANING = {
    "BLOCK": "Blocked — a prohibited practice or a hard security rule. This check fails.",
    "ASK": "Needs a human decision before this can proceed.",
    "WARN": "Allowed to continue — this is a high-risk use; the obligations below are required before deployment.",
    "ALLOW": "No compliance action required.",
}

_ARTEFACT_LABEL = {
    "risk_management": "Risk management system (EU AI Act Art. 9)",
    "dpia": "Data Protection Impact Assessment (GDPR Art. 35)",
    "fria": "Fundamental Rights Impact Assessment (EU AI Act Art. 27)",
    "oversight_plan": "Human-oversight plan (EU AI Act Art. 14)",
    "eval_report": "Evaluation / accuracy report (EU AI Act Art. 15)",
    "worker_information": "Worker information (EU AI Act Art. 26(7); § 87 BetrVG)",
}


def _badge(decision: str) -> str:
    return f"**{decision}** — {_MEANING.get(decision, '')}"


def _rules_section(result: CiResult) -> list[str]:
    if not result.reasons:
        return ["No compliance rules fired."]
    lines = ["| Rule | Decision | Legal source |", "|---|---|---|"]
    for r in result.reasons:
        cid = r.get("check_id") or "—"
        dec = r.get("decision", "")
        src = r.get("source", "")
        title = r.get("title", "")
        src_cell = f"{src}" if src else ""
        if title:
            src_cell = f"{src_cell} — {title}" if src_cell else title
        lines.append(f"| `{cid}` | {dec} | {src_cell} |")
    return lines


def _checklist_section(result: CiResult) -> list[str]:
    if not result.obligations:
        return []
    missing = set(result.missing_artefacts)
    lines = [
        "",
        "### Pending obligations",
        "",
        f"This use case requires {len(result.obligations)} artefact(s) before deployment. "
        "Record each one's path in `.guardrails/use-case.yaml` under `artefacts`.",
        "",
    ]
    for key in result.obligations:
        label = _ARTEFACT_LABEL.get(key, key)
        box = "[ ]" if key in missing else "[x]"
        state = "missing" if key in missing else "present"
        lines.append(f"- {box} **{key}** — {label} ({state})")
    return lines


def _tools_section(tools: list[ToolResult]) -> list[str]:
    lines = ["", "### Scanner status", "", "| Scanner | Status | Detail |", "|---|---|---|"]
    for t in tools:
        lines.append(f"| {t.name} | {t.status} | {t.detail} |")
    return lines


def _files_section(changed_paths: list[str]) -> list[str]:
    if not changed_paths:
        return ["", "### Changed files", "", "(none)"]
    lines = ["", "### Changed files", ""]
    for p in changed_paths:
        lines.append(f"- `{p}`")
    return lines


def render_report(result: CiResult, *, tools: list[ToolResult], changed_paths: list[str],
                  use_case_id: str | None = None) -> str:
    lines: list[str] = []
    lines.append("## EU AI compliance — CI gate")
    lines.append("")
    lines.append("> Halvaro Payments GmbH (fictional). Synthetic data only; not legal advice, not a conformity claim.")
    lines.append("")
    lines.append(_badge(result.decision))
    lines.append("")
    if use_case_id:
        lines.append(f"Declared use case: `{use_case_id}`.")
        lines.append("")
    if result.local_secret:
        lines.append("A secret was detected in the added lines by the built-in scanner. "
                     "Remove it and use a vault or environment variable. This alone fails the check.")
        lines.append("")

    lines.append("### Rules")
    lines.append("")
    lines += _rules_section(result)

    lines += _checklist_section(result)
    lines += _tools_section(tools)
    lines += _files_section(changed_paths)
    lines.append("")
    return "\n".join(lines) + "\n"
