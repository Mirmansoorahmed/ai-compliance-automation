"""Minimal JSON Schema validator (dependency-free).

Supports the Draft-07 subset our register schemas use:
``type`` (object/array/string/integer/boolean/null), ``required``,
``properties``, ``additionalProperties`` (bool), ``enum``, ``pattern``,
``items``, ``minItems``, and a ``format: date`` check (YYYY-MM-DD).

It returns a list of human-readable error strings (empty = valid), so callers
can report every problem at once instead of only the first.

This exists because the sandbox/offline oss profile cannot ``pip install
jsonschema``. If ``jsonschema`` is installed it could be used instead; this
module is the guaranteed path and is intentionally small and strict.
"""

from __future__ import annotations

import re
from typing import Any

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _type_ok(value: Any, type_name: str) -> bool:
    check = _TYPE_CHECKS.get(type_name)
    return bool(check and check(value))


def _validate(value: Any, schema: dict, path: str, errors: list[str]) -> None:
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(value, tn) for tn in types):
            errors.append(f"{path or '<root>'}: expected type {t}, got {type(value).__name__}")
            return  # further checks assume the type matched

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} not in enum {schema['enum']}")

    if schema.get("format") == "date" and isinstance(value, str):
        if not _DATE_RE.match(value):
            errors.append(f"{path}: value {value!r} is not a YYYY-MM-DD date")

    if "pattern" in schema and isinstance(value, str):
        if not re.search(schema["pattern"], value):
            errors.append(f"{path}: value {value!r} does not match pattern {schema['pattern']!r}")

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path or '<root>'}: missing required field {req!r}")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path or '<root>'}: unexpected field {key!r}")
        for key, subschema in props.items():
            if key in value:
                child = f"{path}.{key}" if path else key
                _validate(value[key], subschema, child, errors)

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: expected at least {schema['minItems']} items, got {len(value)}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                _validate(item, item_schema, f"{path}[{i}]", errors)


def validate(value: Any, schema: dict) -> list[str]:
    """Return a list of validation error strings (empty means valid)."""
    errors: list[str] = []
    _validate(value, schema, "", errors)
    return errors
