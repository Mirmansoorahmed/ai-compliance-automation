"""Load use-case.yaml fixtures into a registry {id: dict} for /v1/check.

Reads every *.yaml under a directory (default: fixtures/use-cases/) with the
dependency-free register YAML reader.
"""

from __future__ import annotations

from pathlib import Path

from aca.register.yamlio import load_yaml

_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "use-cases"


def load_registry(directory: str | Path | None = None) -> dict[str, dict]:
    base = Path(directory) if directory is not None else _DEFAULT_DIR
    registry: dict[str, dict] = {}
    if not base.exists():
        return registry
    for path in sorted(base.glob("*.yaml")):
        doc = load_yaml(path)
        if isinstance(doc, dict) and doc.get("id"):
            registry[doc["id"]] = doc
    return registry
