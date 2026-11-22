"""Minimal YAML reader for the register (dependency-free).

The oss profile must run on the standard library alone, so we cannot rely on
PyYAML being installed. This parser supports the restricted YAML subset our
requirement/interpretation files use:

- mappings with ``key: value``
- nested mappings by indentation (two spaces per level)
- block sequences (``- item`` and ``- key: value`` maps)
- scalars: plain strings, quoted strings, integers, booleans, null
- ``#`` line comments

If PyYAML happens to be installed, it is used instead (it is a strict
superset of what we need). To keep results identical with and without PyYAML,
the PyYAML path uses a loader with the timestamp resolver removed, so values
like ``effective_from: 2026-11-14`` load as strings (as the subset parser does)
rather than as ``datetime.date`` objects. The subset parser is the guaranteed
path.

This is deliberately small and strict: it raises on anything it does not
understand rather than guessing, so a malformed register file fails loudly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only when PyYAML is installed
    import yaml as _pyyaml
except Exception:  # pragma: no cover
    _pyyaml = None


def _build_string_date_loader():  # pragma: no cover - requires PyYAML
    """A SafeLoader that does not coerce dates/times into datetime objects.

    PyYAML's default resolver turns ``2026-11-14`` into ``datetime.date`` and
    ``...T...`` strings into ``datetime.datetime``. Our schema expects plain
    strings, so we drop the ``tag:yaml.org,2002:timestamp`` implicit resolver.
    The result matches the dependency-free subset parser exactly.
    """

    class _StringDateLoader(_pyyaml.SafeLoader):
        pass

    timestamp_tag = "tag:yaml.org,2002:timestamp"
    for first_char, resolvers in list(_StringDateLoader.yaml_implicit_resolvers.items()):
        filtered = [(tag, regexp) for (tag, regexp) in resolvers if tag != timestamp_tag]
        _StringDateLoader.yaml_implicit_resolvers[first_char] = filtered
    return _StringDateLoader


_STRING_DATE_LOADER = _build_string_date_loader() if _pyyaml is not None else None


class YamlError(ValueError):
    """Raised when the register YAML cannot be parsed."""


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
    # Only strip comments that are not inside quotes. Our files never put '#'
    # inside a quoted scalar, but guard the common case anyway.
    in_single = in_double = False
    out = []
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
    return "".join(out)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_block(lines: list[tuple[int, str]], pos: int, indent: int):
    """Parse a mapping or sequence at the given indent. Returns (value, pos)."""
    # Look at the first meaningful line to decide mapping vs sequence.
    if pos >= len(lines):
        return None, pos
    _, first = lines[pos]
    if first.lstrip().startswith("- "):
        return _parse_sequence(lines, pos, indent)
    return _parse_mapping(lines, pos, indent)


def _parse_mapping(lines: list[tuple[int, str]], pos: int, indent: int):
    result: dict[str, Any] = {}
    while pos < len(lines):
        ind, line = lines[pos]
        if ind < indent:
            break
        if ind > indent:
            raise YamlError(f"unexpected indent at: {line!r}")
        content = line.strip()
        if ":" not in content:
            raise YamlError(f"expected 'key: value' at: {line!r}")
        key, _, rest = content.partition(":")
        key = key.strip()
        rest = rest.strip()
        pos += 1
        if rest == "":
            # Nested block (mapping or sequence) at deeper indent, or empty.
            if pos < len(lines) and lines[pos][0] > indent:
                child_indent = lines[pos][0]
                # Sequences may be indented at the same level as the key in YAML.
                if lines[pos][1].lstrip().startswith("- ") and lines[pos][0] >= indent:
                    value, pos = _parse_sequence(lines, pos, lines[pos][0])
                else:
                    value, pos = _parse_block(lines, pos, child_indent)
                result[key] = value
            elif pos < len(lines) and lines[pos][1].lstrip().startswith("- ") and lines[pos][0] == indent:
                value, pos = _parse_sequence(lines, pos, indent)
                result[key] = value
            else:
                result[key] = None
        else:
            result[key] = _scalar(rest)
    return result, pos


def _parse_sequence(lines: list[tuple[int, str]], pos: int, indent: int):
    result: list[Any] = []
    while pos < len(lines):
        ind, line = lines[pos]
        if ind < indent or not line.lstrip().startswith("- "):
            break
        if ind > indent:
            raise YamlError(f"unexpected indent in sequence at: {line!r}")
        item = line.lstrip()[2:].strip()
        if item == "":
            raise YamlError(f"empty sequence item at: {line!r}")
        if ":" in item and not (item[0] in ("'", '"')):
            # Inline mapping start: treat the item line as the first key of a map.
            key, _, rest = item.partition(":")
            m: dict[str, Any] = {key.strip(): _scalar(rest) if rest.strip() else None}
            pos += 1
            # Continuation keys are indented deeper than the dash.
            cont_indent = indent + 2
            while pos < len(lines) and lines[pos][0] >= cont_indent and not lines[pos][1].lstrip().startswith("- "):
                sub, pos2 = _parse_mapping(lines, pos, lines[pos][0])
                m.update(sub)
                pos = pos2
                break
            result.append(m)
        else:
            result.append(_scalar(item))
            pos += 1
    return result, pos


def _parse_subset(text: str) -> Any:
    raw_lines = text.splitlines()
    lines: list[tuple[int, str]] = []
    for raw in raw_lines:
        stripped = _strip_comment(raw).rstrip()
        if stripped.strip() == "" or stripped.strip() == "---":
            continue
        lines.append((_indent(stripped), stripped))
    if not lines:
        return None
    value, pos = _parse_block(lines, 0, lines[0][0])
    if pos != len(lines):
        raise YamlError(f"unparsed trailing content starting at line: {lines[pos][1]!r}")
    return value


def loads_yaml(text: str) -> Any:
    """Parse YAML text. Dates load as strings on both the PyYAML and subset path."""
    if _pyyaml is not None:  # pragma: no cover - exercised only when PyYAML present
        return _pyyaml.load(text, Loader=_STRING_DATE_LOADER)
    return _parse_subset(text)


def load_yaml(path: str | Path) -> Any:
    return loads_yaml(Path(path).read_text(encoding="utf-8"))
