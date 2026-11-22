"""Validate a use-case.yaml document (Phase 1).

Per-field JSON Schema plus a cross-field invariant from the Art. 6(3) rule: an
Annex III exception cannot be claimed while the system profiles people
(``art6_3_exception: true`` with ``profiling: true`` is invalid).

Returns a list of error strings (empty = valid).
"""

from __future__ import annotations

import json
from pathlib import Path

from aca.register.jsonschema_min import validate as schema_validate
from aca.register.yamlio import load_yaml, loads_yaml

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas"


def _load_schema() -> dict:
    return json.loads((_SCHEMA_DIR / "use-case.schema.json").read_text(encoding="utf-8"))


def validate_use_case(doc: dict) -> list[str]:
    errors = list(schema_validate(doc, _load_schema()))
    # Art. 6(3): the exception cannot apply when the system profiles people.
    if doc.get("art6_3_exception") is True and doc.get("profiling") is True:
        errors.append(
            "art6_3_exception cannot be true while profiling is true (Art. 6(3))"
        )
    return errors


def validate_use_case_text(text: str) -> list[str]:
    doc = loads_yaml(text)
    if not isinstance(doc, dict):
        return ["use-case.yaml must be a mapping"]
    return validate_use_case(doc)


def validate_use_case_file(path: str | Path) -> list[str]:
    doc = load_yaml(path)
    if not isinstance(doc, dict):
        return [f"{path}: use-case.yaml must be a mapping"]
    return validate_use_case(doc)
