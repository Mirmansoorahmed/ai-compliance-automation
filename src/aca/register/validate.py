"""Register validation: JSON Schema + cross-file invariants (R1, R2).

Invariants enforced beyond per-file schema:

- R1.5  ``rule_ref`` on a requirement requires ``mode`` in {auto, hybrid} AND an
        approved interpretation for that requirement.
- R2.2  an interpretation's ``requirement_id`` must resolve to a requirement.
- R2.3  approved interpretations are immutable: two approved records that share
        an ``id`` must share an identical body except ``version`` differs — in
        practice each approved change is a new version, so a duplicated
        (id, version) with differing bodies is a violation.
- R2.4  a hard deny (``decision: confirmed_prohibited_pattern``) is only valid
        when ``status: approved``.
- R2.5  every path in ``eval_cases`` must exist on disk.

Usage:
    python -m aca.register.validate requirements interpretations
Exits non-zero (and prints every error) on any failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from aca.register.jsonschema_min import validate as schema_validate
from aca.register.yamlio import load_yaml

_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas"
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_schema(name: str) -> dict:
    return json.loads((_SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _yaml_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.glob("*.yaml"))


def validate_register(
    requirements_dir: str | Path,
    interpretations_dir: str | Path,
    *,
    repo_root: Path | None = None,
) -> list[str]:
    """Validate the whole register. Returns a list of error strings."""
    req_dir = Path(requirements_dir)
    int_dir = Path(interpretations_dir)
    root = repo_root or _REPO_ROOT
    errors: list[str] = []

    req_schema = _load_schema("requirement.schema.json")
    int_schema = _load_schema("interpretation.schema.json")

    requirements: dict[str, dict] = {}
    for path in _yaml_files(req_dir):
        doc = load_yaml(path)
        for e in schema_validate(doc, req_schema):
            errors.append(f"{path.name}: {e}")
        if isinstance(doc, dict) and "id" in doc:
            if doc["id"] in requirements:
                errors.append(f"{path.name}: duplicate requirement id {doc['id']!r}")
            requirements[doc["id"]] = doc

    interpretations: list[dict] = []
    approved_by_key: dict[tuple[str, Any], dict] = {}
    for path in _yaml_files(int_dir):
        doc = load_yaml(path)
        for e in schema_validate(doc, int_schema):
            errors.append(f"{path.name}: {e}")
        if not isinstance(doc, dict):
            continue
        interpretations.append(doc)

        # R2.2 — FK resolves.
        rid = doc.get("requirement_id")
        if rid and rid not in requirements:
            errors.append(f"{path.name}: requirement_id {rid!r} does not resolve")

        # R2.4 — confirmed_prohibited_pattern must be approved.
        if doc.get("decision") == "confirmed_prohibited_pattern" and doc.get("status") != "approved":
            errors.append(
                f"{path.name}: confirmed_prohibited_pattern requires status 'approved'"
            )

        # R2.3 — approved immutability: same (id, version) must not differ.
        if doc.get("status") == "approved":
            key = (doc.get("id"), doc.get("version"))
            prev = approved_by_key.get(key)
            if prev is not None and prev != doc:
                errors.append(
                    f"{path.name}: approved interpretation {key} differs from another "
                    f"file with the same id+version (approved records are immutable)"
                )
            approved_by_key[key] = doc

        # R2.5 — eval_cases paths exist.
        for case in doc.get("eval_cases") or []:
            if not (root / case).exists():
                errors.append(f"{path.name}: eval_case path {case!r} does not exist")

    # R1.5 — rule_ref invariant on requirements.
    approved_req_ids = {
        d.get("requirement_id")
        for d in interpretations
        if d.get("status") == "approved"
    }
    for rid, doc in requirements.items():
        if doc.get("rule_ref"):
            if doc.get("mode") not in ("auto", "hybrid"):
                errors.append(
                    f"{rid}: rule_ref set but mode is {doc.get('mode')!r} "
                    f"(must be 'auto' or 'hybrid')"
                )
            if rid not in approved_req_ids:
                errors.append(
                    f"{rid}: rule_ref set but no approved interpretation exists"
                )

    return errors


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        print("usage: python -m aca.register.validate <requirements_dir> <interpretations_dir>")
        return 2
    errors = validate_register(argv[0], argv[1])
    if errors:
        print(f"register validation FAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("register validation OK")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
