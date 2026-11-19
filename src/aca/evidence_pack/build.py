"""Build the evidence pack v2 (text + PDF).

Assembles the trace, renders the auditor view (clean of code/paths/hashes), and
writes the PDF with the existing report PDF writer. Fails closed if the body
would contain a path, hash or code block.
"""

from __future__ import annotations

from pathlib import Path

from aca.evidence_pack.collect import build_trace
from aca.evidence_pack.render import render_text
from aca.report.pdf import write_pdf

_REPO = Path(__file__).resolve().parents[3]


def build_evidence_pack(*, out_path: str | Path | None = None) -> Path:
    trace = build_trace()
    text = render_text(trace)  # raises EvidencePackError if not clean
    out = Path(out_path) if out_path else (_REPO / "report" / "evidence-pack-v2.pdf")
    return write_pdf(text, out)


def main() -> int:  # pragma: no cover - CLI glue
    path = build_evidence_pack()
    print(f"evidence pack v2 written: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
