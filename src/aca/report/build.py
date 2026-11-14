"""Evidence pack report builder (R13).

Assembles the requirement map, coverage figures, the latest committed eval
results (or "not measured"), and a short decision-log excerpt from fixture
spans, then renders a PDF. Fails closed (``ReportError``, no PDF) if a required
field is missing. Carries the project disclaimers.

No invented metrics: eval figures come only from a committed run via
``aca.eval.metrics``; absent metrics render as TO BE MEASURED.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aca.eval.coverage import compute_coverage
from aca.eval.metrics import latest_run, provenance_line, results_table
from aca.register.yamlio import load_yaml
from aca.report.pdf import write_pdf

_REPO = Path(__file__).resolve().parents[3]

DISCLAIMER = (
    "Lab / portfolio project. Synthetic data only (fictional firms Northwind "
    "Advisory and NordPay). Mappings to the EU AI Act and ISO/IEC 27001:2022 are "
    "illustrative and in our own words; this is not legal advice and not a "
    "conformity claim."
)

# A row is required to have these fields or the report fails closed.
_REQUIRED_REQ_FIELDS = ("id", "citation", "title", "mode")


class ReportError(RuntimeError):
    """Raised when the report cannot be built from complete, valid data."""


@dataclass
class ReportInputs:
    requirements: list[dict]
    coverage: dict
    eval_run: dict | None
    spans: list[dict]


def _load_requirements(repo: Path) -> list[dict]:
    reqs = [load_yaml(p) for p in sorted((repo / "requirements").glob("*.yaml"))]
    if not reqs:
        raise ReportError("no requirements found; cannot build report")
    for r in reqs:
        missing = [f for f in _REQUIRED_REQ_FIELDS if not r.get(f)]
        if missing:
            raise ReportError(f"requirement {r.get('id', '?')} missing fields: {missing}")
    return reqs


def _load_spans(repo: Path) -> list[dict]:
    path = repo / "fixtures" / "demo_spans.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def gather_inputs(repo: Path | None = None) -> ReportInputs:
    repo = repo or _REPO
    requirements = _load_requirements(repo)
    coverage = compute_coverage(repo / "requirements", floor_file=repo / "eval" / "coverage_floor.json").to_dict()
    run = latest_run(repo / "eval" / "results")
    spans = _load_spans(repo)
    return ReportInputs(requirements=requirements, coverage=coverage, eval_run=run, spans=spans)


def render_text(inputs: ReportInputs) -> str:
    lines: list[str] = []
    lines.append("AI Compliance Automation — Evidence Pack")
    lines.append("Core component: Semantic Guard (emits labels; OPA decides).")
    lines.append("")
    lines.append(DISCLAIMER)
    lines.append("")
    lines.append("=" * 72)
    lines.append("1. Requirement map (illustrative; titles in our own words)")
    lines.append("=" * 72)
    lines.append(f"{'ID':<18}{'Citation':<22}{'Mode':<8}Title")
    for r in inputs.requirements:
        lines.append(f"{r['id']:<18}{r['citation']:<22}{r.get('mode',''):<8}{r['title']}")
    lines.append("")
    lines.append("=" * 72)
    lines.append("2. Coverage")
    lines.append("=" * 72)
    c = inputs.coverage
    lines.append(f"mapped: {c['pct_mapped']}%   auto: {c['pct_auto']}%   "
                 f"human: {c['pct_human']}%   hybrid: {c['pct_hybrid']}%")
    lines.append(f"floor: {c['floor']}% ({c['floor_note']}) — passes: {c['passes_floor']}")
    lines.append("")
    lines.append("=" * 72)
    lines.append("3. Eval results")
    lines.append("=" * 72)
    if inputs.eval_run is None:
        lines.append("Not measured — no committed eval run.")
    else:
        lines.extend(results_table(inputs.eval_run))
    lines.append(provenance_line(inputs.eval_run))
    lines.append("NOTE: the committed oss run uses a deterministic hashed-vector")
    lines.append("embedding fallback, not a trained model — a reproducible baseline,")
    lines.append("not a claim about real detector quality.")
    lines.append("")
    lines.append("=" * 72)
    lines.append("4. Decision log excerpt (from fixture spans)")
    lines.append("=" * 72)
    if not inputs.spans:
        lines.append("No fixture spans available.")
    else:
        for s in inputs.spans[:10]:
            a = s.get("attributes", {})
            lines.append(
                f"- {a.get('tier','?'):<10} resource={a.get('resource','?')} "
                f"action={a.get('action','?')} subject={a.get('subject_pseudonym','?')} "
                f"reason={a.get('reason_code','?')}"
            )
    lines.append("")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def build_report(*, repo: Path | None = None, out_path: str | Path | None = None) -> Path:
    repo = repo or _REPO
    inputs = gather_inputs(repo)
    text = render_text(inputs)
    out = Path(out_path) if out_path else (repo / "report" / "evidence-pack.pdf")
    return write_pdf(text, out)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI glue
    try:
        path = build_report()
    except ReportError as exc:
        print(f"report FAILED (closed): {exc}")
        return 1
    print(f"report written: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
