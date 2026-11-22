"""Validate policy/catalog/catalog.yaml (Phase 0).

Checks, beyond per-row JSON Schema:
- ids are unique,
- every row's decision is BLOCK | ASK | WARN | ALLOW,
- every row has a non-empty source (`src`) and enforcement points (`ep`),
- enforcement-point tokens are from the known set (IDE, AGT, CI, DEP, RT, ORG).

Returns a list of error strings (empty = valid).
"""

from __future__ import annotations

import json
from pathlib import Path

from aca.catalog.loader import load_catalog
from aca.register.jsonschema_min import validate as schema_validate

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas"
VALID_DECISIONS = ("BLOCK", "ASK", "WARN", "ALLOW")
VALID_EP = ("IDE", "AGT", "CI", "DEP", "RT", "ORG")


def _load_schema() -> dict:
    return json.loads((_SCHEMA_DIR / "catalog-check.schema.json").read_text(encoding="utf-8"))


def validate_catalog(path: str | Path | None = None) -> list[str]:
    errors: list[str] = []
    data = load_catalog(path)
    checks = data.get("checks") or []
    schema = _load_schema()

    if not checks:
        return ["catalog has no checks"]

    seen: set[str] = set()
    for i, check in enumerate(checks):
        where = check.get("id") or f"row {i}"
        for e in schema_validate(check, schema):
            errors.append(f"{where}: {e}")

        cid = check.get("id")
        if cid:
            if cid in seen:
                errors.append(f"{cid}: duplicate id")
            seen.add(cid)

        if check.get("dec") not in VALID_DECISIONS:
            errors.append(f"{where}: decision {check.get('dec')!r} not in {VALID_DECISIONS}")

        if not (check.get("src") or "").strip():
            errors.append(f"{where}: missing source (src)")

        ep_raw = (check.get("ep") or "").strip()
        if not ep_raw:
            errors.append(f"{where}: missing enforcement points (ep)")
        else:
            for token in [t.strip() for t in ep_raw.split(",") if t.strip()]:
                if token not in VALID_EP:
                    errors.append(f"{where}: unknown enforcement point {token!r} (valid: {VALID_EP})")

    return errors


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI glue
    errors = validate_catalog()
    if errors:
        print(f"catalog validation FAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("catalog validation OK")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
