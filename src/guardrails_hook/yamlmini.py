"""A tiny, dependency-free YAML reader for the hook's use-case.yaml.

Supports the restricted subset use-case.yaml uses: ``key: value`` mappings,
block sequences (``- item``), nested mappings by indentation, scalars (plain /
quoted strings, ints, booleans, null), inline empty ``[]``/``{}``, and ``#``
comments. It raises on nothing — a malformed file returns what it parsed — so
the hook never crashes the host tool. The policy service re-validates fully.

Kept inside the hook package so ``guardrails-hook`` has no dependency on the
``aca`` package or PyYAML when installed on a developer machine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _scalar(token: str) -> Any:
    token = token.strip()
    if token == "" or token in ("~", "null", "Null", "NULL"):
        return None
    if token == "[]":
        return []
    if token == "{}":
        return {}
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1]
    low = token.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if token.lstrip("-").isdigit():
        return int(token)
    return token


def _strip_comment(line: str) -> str:
    in_s = in_d = False
    out = []
    for ch in line:
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "#" and not in_s and not in_d:
            break
        out.append(ch)
    return "".join(out)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_block(lines, pos, indent):
    if pos >= len(lines):
        return None, pos
    if lines[pos][1].lstrip().startswith("- "):
        return _parse_seq(lines, pos, indent)
    return _parse_map(lines, pos, indent)


def _parse_map(lines, pos, indent):
    result: dict = {}
    while pos < len(lines):
        ind, line = lines[pos]
        if ind < indent:
            break
        content = line.strip()
        if ":" not in content:
            break
        key, _, rest = content.partition(":")
        key = key.strip()
        rest = rest.strip()
        pos += 1
        if rest == "":
            if pos < len(lines) and lines[pos][1].lstrip().startswith("- ") and lines[pos][0] >= indent:
                value, pos = _parse_seq(lines, pos, lines[pos][0])
            elif pos < len(lines) and lines[pos][0] > indent:
                value, pos = _parse_block(lines, pos, lines[pos][0])
            else:
                value = None
            result[key] = value
        else:
            result[key] = _scalar(rest)
    return result, pos


def _parse_seq(lines, pos, indent):
    result: list = []
    while pos < len(lines):
        ind, line = lines[pos]
        if ind != indent or not line.lstrip().startswith("- "):
            break
        item = line.lstrip()[2:].strip()
        result.append(_scalar(item))
        pos += 1
    return result, pos


def loads_yaml(text: str) -> Any:
    lines = []
    for raw in text.splitlines():
        stripped = _strip_comment(raw).rstrip()
        if stripped.strip() in ("", "---"):
            continue
        lines.append((_indent(stripped), stripped))
    if not lines:
        return None
    value, _ = _parse_block(lines, 0, lines[0][0])
    return value


def load_yaml_file(path: str | Path) -> Any:
    return loads_yaml(Path(path).read_text(encoding="utf-8"))
