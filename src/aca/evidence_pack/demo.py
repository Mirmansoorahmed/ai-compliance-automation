"""Demo: print the evidence pack v2 auditor view (Phase 7), offline.

Shows one use case from prompt to production: the ordered decision trace across
the editor, CI, deploy and runtime, the obligations + approvals, and the ISO
42001 / EU AI Act mapping. No code, paths or hashes in the body.
"""

from __future__ import annotations

from aca.evidence_pack.collect import build_trace
from aca.evidence_pack.render import render_text


def main() -> int:
    print(render_text(build_trace()))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
