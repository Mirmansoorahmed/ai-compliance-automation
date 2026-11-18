"""Dependency-free loader for policy/catalog/catalog.yaml.

The catalog is a top-level mapping ``{version, checks: [ {..}, {..} ]}`` where
each check is a flat mapping of string keys to string scalars. The oss profile
has no PyYAML, so this loader parses that restricted shape directly and also
folds soft-wrapped continuation lines (a line indented deeper than its ``key:``
line, not starting with ``-``) back into the scalar, so both the single-line and
the editor-wrapped forms parse identically.

If PyYAML is installed it is used instead (strict superset); otherwise the
built-in parser runs. Either way the result is the same Python structure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only when PyYAML is installed
    import yaml as _pyyaml
except Exception:  # pragma: no cover
    _pyyaml = None

_CATALOG_PATH = Path(__file__).resolve().parents[3] / "policy" / "catalog" / "catalog.yaml"

# Keys every check row carries (used to recognise a new key vs a wrapped line).
_KNOWN_KEYS = (
    "law", "grp", "id", "src", "url", "title", "trigger",
    "en", "de", "dec", "art", "det", "sem", "ep", "status",
)


class CatalogError(ValueError):
    """Raised when the catalog cannot be parsed."""


def _unquote(token: str) -> str:
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        inner = token[1:-1]
        if token[0] == "'":
            return inner.replace("''", "'")
        return inner
    return token


def _looks_like_key(stripped: str) -> str | None:
    """Return the key name if the line starts a ``known_key:`` mapping entry."""
    if ":" not in stripped:
        return None
    candidate = stripped.split(":", 1)[0].strip()
    return candidate if candidate in _KNOWN_KEYS else None


def _parse_subset(text: str) -> dict:
    version: str | None = None
    checks: list[dict] = []
    current: dict | None = None
    last_key: str | None = None

    lines = text.splitlines()
    i = 0
    # Top-level: optional "version:" then "checks:".
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if stripped == "" or stripped.startswith("#"):
            i += 1
            continue
        if stripped.startswith("version:"):
            version = _unquote(stripped.split(":", 1)[1])
            i += 1
            continue
        if stripped == "checks:":
            i += 1
            break
        i += 1

    for raw in lines[i:]:
        stripped = raw.strip()
        if stripped == "" or stripped.startswith("#"):
            continue

        if stripped.startswith("- "):
            # New check row begins; "- key: value".
            current = {}
            checks.append(current)
            body = stripped[2:].strip()
            key, _, val = body.partition(":")
            key = key.strip()
            if key not in _KNOWN_KEYS:
                raise CatalogError(f"unexpected first key in check row: {key!r}")
            current[key] = _unquote(val)
            last_key = key
            continue

        if current is None:
            raise CatalogError(f"content before first check row: {stripped!r}")

        key = _looks_like_key(stripped)
        if key is not None:
            _, _, val = stripped.partition(":")
            current[key] = _unquote(val)
            last_key = key
        else:
            # Soft-wrapped continuation of the previous scalar.
            if last_key is None:
                raise CatalogError(f"dangling continuation line: {stripped!r}")
            prev = current.get(last_key, "")
            current[last_key] = (str(prev) + " " + stripped).strip()

    return {"version": version, "checks": checks}


def load_catalog_text(text: str) -> dict:
    if _pyyaml is not None:  # pragma: no cover - requires PyYAML
        data = _pyyaml.safe_load(text)
        return {"version": data.get("version"), "checks": list(data.get("checks") or [])}
    return _parse_subset(text)


def load_catalog(path: str | Path | None = None) -> dict:
    p = Path(path) if path is not None else _CATALOG_PATH
    return load_catalog_text(p.read_text(encoding="utf-8"))


def catalog_path() -> Path:
    return _CATALOG_PATH
