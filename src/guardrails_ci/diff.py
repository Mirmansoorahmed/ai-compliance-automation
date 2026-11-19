"""Parse a unified diff into changed files and their added lines.

Dependency-free. Understands the parts of ``git diff`` output the gate needs:
the ``+++ b/<path>`` file headers and the added (``+``) content lines, skipping
the ``+++`` header itself. Deleted files and removed lines are ignored — the
gate reasons about what the PR *introduces*.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileChange:
    path: str
    added_lines: list[str] = field(default_factory=list)

    @property
    def added_text(self) -> str:
        return "\n".join(self.added_lines)


@dataclass
class Diff:
    files: list[FileChange] = field(default_factory=list)

    @property
    def changed_paths(self) -> list[str]:
        return [f.path for f in self.files]

    @property
    def added_text(self) -> str:
        """All added lines across every file, newline-joined."""
        return "\n".join(f.added_text for f in self.files)

    def file(self, path: str) -> FileChange | None:
        for f in self.files:
            if f.path == path:
                return f
        return None


def _strip_ab_prefix(path: str) -> str:
    # git uses a/ and b/ prefixes; also tolerate quoted paths.
    path = path.strip()
    if path.startswith(('"', "'")) and path.endswith(('"', "'")):
        path = path[1:-1]
    for pre in ("a/", "b/"):
        if path.startswith(pre):
            return path[len(pre):]
    return path


def parse_diff(text: str) -> Diff:
    """Parse unified-diff text into a Diff of changed files + added lines."""
    diff = Diff()
    current: FileChange | None = None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            current = None
            continue
        if line.startswith("+++ "):
            target = line[4:].strip()
            if target == "/dev/null":
                current = None  # file deleted
                continue
            current = FileChange(path=_strip_ab_prefix(target))
            diff.files.append(current)
            continue
        if line.startswith("--- "):
            continue
        if line.startswith("@@"):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            if current is not None:
                current.added_lines.append(line[1:])
    return diff


def diff_from_file(path: str | Path) -> Diff:
    return parse_diff(Path(path).read_text(encoding="utf-8"))


def diff_from_refs(base: str, head: str, *, repo: str | Path | None = None) -> Diff:
    """Run ``git diff base...head`` and parse it. Raises on a git error."""
    cmd = ["git", "diff", "--unified=0", f"{base}...{head}"]
    out = subprocess.run(
        cmd, cwd=str(repo) if repo else None,
        check=True, capture_output=True, text=True,
    )
    return parse_diff(out.stdout)
