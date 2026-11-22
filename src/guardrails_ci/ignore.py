"""Optional ``.guardrails/ignore`` support for the CI gate.

The gate scans the PR diff. A repo whose own test corpus deliberately contains
attack text and synthetic secrets (``eval/`` cases, ``tests/fixtures/`` secret
diffs) would otherwise BLOCK on its own fixtures. ``.guardrails/ignore`` lets a
repo drop such paths from the scan *without weakening the gate for real code*:
excluded paths are removed before the secret scan and the /v1/check engine ever
see them, and the report lists exactly what was excluded so the exclusion is
auditable in the PR.

Format: gitignore-style, dependency-free.
  - blank lines and lines beginning with ``#`` are ignored (a trailing comment
    is *not* stripped — ``#`` only starts a comment at column 0, matching git);
  - a trailing ``/`` matches a directory and everything under it;
  - ``**`` matches across path segments; ``*`` and ``?`` are the usual globs;
  - a pattern with no ``/`` matches the basename at any depth;
  - a pattern containing ``/`` is anchored to the repo root.

The ignore file itself (``.guardrails/ignore``) is never excluded, so a PR that
touches it is always scanned and the change is visible in the report.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEFAULT_REL_PATH = PurePosixPath(".guardrails") / "ignore"


@dataclass
class IgnoreSpec:
    """Compiled patterns from a ``.guardrails/ignore`` file."""

    patterns: list[str]
    #: present=True when the file exists on disk (empty patterns is still a
    #: real, if no-op, file); used so the report can distinguish "no file" from
    #: "file with only comments".
    present: bool = False

    def matches(self, path: str) -> bool:
        return _matches_any(path, self.patterns)


def parse_patterns(text: str) -> list[str]:
    """Parse ignore-file text into a list of glob patterns."""
    patterns: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped)
    return patterns


def load_ignore(repo: str | Path = ".") -> IgnoreSpec:
    """Load ``<repo>/.guardrails/ignore`` if present, else an empty spec."""
    path = Path(repo) / DEFAULT_REL_PATH
    if not path.is_file():
        return IgnoreSpec(patterns=[], present=False)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return IgnoreSpec(patterns=[], present=False)
    return IgnoreSpec(patterns=parse_patterns(text), present=True)


def _normalise(path: str) -> str:
    # Repo-relative, POSIX separators, no leading "./".
    p = path.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def _pattern_matches(path: str, pattern: str) -> bool:
    path = _normalise(path)
    pat = pattern.strip().replace("\\", "/")
    if not pat:
        return False

    anchored = "/" in pat.rstrip("/")
    dir_only = pat.endswith("/")
    pat = pat.rstrip("/").lstrip("/")
    if not pat:
        return False

    if dir_only:
        # "foo/" matches foo/ and everything under it.
        if anchored:
            return path == pat or path.startswith(pat + "/")
        # Unanchored dir: match the directory at any depth.
        parts = PurePosixPath(path).parts
        return any(_seg_glob(seg, pat) for seg in parts[:-1]) or _prefix_at_any_depth(path, pat)

    if anchored:
        return _glob(path, pat)

    # Unanchored, no slash: match the basename at any depth, or (with **) the
    # whole path.
    if "/" not in pat:
        return _seg_glob(PurePosixPath(path).name, pat) or _glob(path, "**/" + pat)
    return _glob(path, pat) or _glob(path, "**/" + pat)


def _prefix_at_any_depth(path: str, directory: str) -> bool:
    # directory may itself contain slashes/**; test every suffix start.
    parts = path.split("/")
    for i in range(len(parts)):
        suffix = "/".join(parts[i:])
        if suffix == directory or suffix.startswith(directory + "/"):
            return True
        if _glob(suffix, directory + "/**"):
            return True
    return False


def _seg_glob(segment: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(segment, pattern)


def _glob(path: str, pattern: str) -> bool:
    """fnmatch with ``**`` handled across path separators."""
    if "**" not in pattern:
        # fnmatch's ``*`` crosses ``/`` too, so guard single-* patterns to not
        # leak across segments when the pattern has no explicit ``**``.
        return _match_no_doublestar(path, pattern)
    # Translate ** to a regex-ish fnmatch: split on ** and match the pieces.
    return _match_with_doublestar(path, pattern)


def _match_no_doublestar(path: str, pattern: str) -> bool:
    # A single * must not cross a "/". Compare segment counts.
    if "/" in pattern:
        p_parts = pattern.split("/")
        t_parts = path.split("/")
        if len(p_parts) != len(t_parts):
            return False
        return all(fnmatch.fnmatchcase(t, p) for t, p in zip(t_parts, p_parts))
    return fnmatch.fnmatchcase(path, pattern)


def _match_with_doublestar(path: str, pattern: str) -> bool:
    import re

    # Build a regex from the glob, treating ** specially.
    regex = _glob_to_regex(pattern)
    return re.fullmatch(regex, path) is not None


def _glob_to_regex(pattern: str) -> str:
    import re

    out = []
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                # ** -> match across separators. Consume an optional trailing /.
                j = i + 2
                if j < n and pattern[j] == "/":
                    out.append("(?:.*/)?")
                    i = j + 1
                    continue
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


def _matches_any(path: str, patterns: list[str]) -> bool:
    path = _normalise(path)
    if path == str(DEFAULT_REL_PATH):
        # The ignore file is never excluded.
        return False
    return any(_pattern_matches(path, pat) for pat in patterns)


def partition_paths(paths: list[str], spec: IgnoreSpec) -> tuple[list[str], list[str]]:
    """Split paths into (kept, excluded) by the ignore spec, order preserved."""
    kept: list[str] = []
    excluded: list[str] = []
    for p in paths:
        (excluded if spec.matches(p) else kept).append(p)
    return kept, excluded


def ignore_file_changed(changed_paths: list[str]) -> bool:
    """True when the PR diff touches ``.guardrails/ignore`` itself."""
    target = str(DEFAULT_REL_PATH)
    return any(_normalise(p) == target for p in changed_paths)
