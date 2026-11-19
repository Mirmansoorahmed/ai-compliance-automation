"""guardrails-ci — the Phase 3 CI gate.

Reads a pull-request diff (git refs or a --diff-file), runs the local secret
scan on added lines, calls the same decision engine as POST /v1/check in-process
(no running service), checks the required artefacts for a WARN use case against
use-case.yaml, and writes a PR-comment-ready ci-report.md plus an AI-BOM.

Exit code is the gate: BLOCK (and ASK, unless --ask-passes) fail the check.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
