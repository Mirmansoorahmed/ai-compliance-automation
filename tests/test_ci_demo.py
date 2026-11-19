"""Phase 3 — the CI demo runs end to end and prints both outcomes."""

import io
from contextlib import redirect_stdout

from guardrails_ci import demo


def test_demo_runs_and_prints_both_cases():
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = demo.main()
    assert rc == 0
    text = buf.getvalue()
    # Secret -> BLOCK exit 1; CV -> WARN exit 0 with a checklist.
    assert "BLOCK" in text
    assert "exit code : 1" in text
    assert "WARN" in text
    assert "exit code : 0" in text
    assert "pending checklist" in text
