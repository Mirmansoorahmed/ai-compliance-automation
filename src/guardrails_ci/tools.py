"""Optional external scanners: gitleaks and Semgrep.

Both are optional. If the binary is not on PATH the scanner is reported as
"skipped (not installed)" and never fails the gate — a missing tool is not a
compliance finding. The authoritative secret signal is the built-in scan
(guardrails_hook.secrets); these add depth when present.

Each runner returns a ToolResult the report renders. A tool that runs and finds
nothing is "clean"; one that finds something is "findings" (surfaced in the
report, but the gate decision still comes from the decision engine so behaviour
is identical whether or not the tool is installed).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class ToolResult:
    name: str
    status: str  # "clean" | "findings" | "skipped" | "error"
    detail: str = ""

    @property
    def installed(self) -> bool:
        return self.status not in ("skipped",)


def _which(binary: str) -> bool:
    return shutil.which(binary) is not None


def run_gitleaks(diff_path: str | None = None) -> ToolResult:
    if not _which("gitleaks"):
        return ToolResult("gitleaks", "skipped", "not installed")
    try:
        # Scan the working tree; detect mode exits non-zero on findings.
        proc = subprocess.run(
            ["gitleaks", "detect", "--no-banner", "--redact"],
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return ToolResult("gitleaks", "error", str(exc))
    if proc.returncode == 0:
        return ToolResult("gitleaks", "clean", "no leaks found")
    return ToolResult("gitleaks", "findings", "gitleaks reported potential secrets")


def run_semgrep(paths: list[str] | None = None) -> ToolResult:
    if not _which("semgrep"):
        return ToolResult("semgrep", "skipped", "not installed")
    args = ["semgrep", "--error", "--quiet", "--config", "auto"]
    if paths:
        args += list(paths)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        return ToolResult("semgrep", "error", str(exc))
    if proc.returncode == 0:
        return ToolResult("semgrep", "clean", "no findings")
    return ToolResult("semgrep", "findings", "semgrep reported findings")


def run_optional_tools(paths: list[str] | None = None) -> list[ToolResult]:
    return [run_gitleaks(), run_semgrep(paths)]
