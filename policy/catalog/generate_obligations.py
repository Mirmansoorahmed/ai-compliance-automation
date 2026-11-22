"""Generate OPA policy data from catalog.yaml.

Writes two files under policy/data/, both derived only from catalog.yaml so the
catalog stays the single source of truth:

- ``catalog.json``     -> {"checks": {id: {"dec": BLOCK|ASK|WARN|ALLOW}}}
- ``obligations.json`` -> {"obligations": {id: [artefact keys]}}

For each check we derive the canonical obligation keys (the artefacts the deploy
gate checks) by matching known phrases in the catalog's ``art`` field.
Deterministic: the same catalog always yields the same JSON. Tests assert the
committed files are up to date.

Obligation keys match use-case.yaml ``artefacts`` keys:
  risk_management, dpia, fria, oversight_plan, eval_report, worker_information
"""

from __future__ import annotations

import json
from pathlib import Path

from aca.catalog.loader import load_catalog

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# (substring in the catalog `art` field) -> canonical obligation key.
_PHRASE_TO_KEY = [
    ("risk-mgmt", "risk_management"),
    ("risk-register", "risk_management"),
    ("risk management", "risk_management"),
    ("dpia", "dpia"),
    # FRIA only when it is a required artefact, not an explanatory aside such as
    # GDPR-35's "(feeds FRIA)". Match the artefact forms used in the catalog.
    ("fria.md", "fria"),
    ("fria (art 27)", "fria"),
    ("+ fria", "fria"),
    ("oversight-plan", "oversight_plan"),
    ("oversight plan", "oversight_plan"),
    ("eval-report", "eval_report"),
    ("worker info", "worker_information"),
    ("worker-information", "worker_information"),
]

_OBLIGATION_ORDER = [
    "risk_management", "dpia", "fria", "oversight_plan", "eval_report", "worker_information",
]


def obligations_for(art: str) -> list[str]:
    low = (art or "").lower()
    keys = {key for phrase, key in _PHRASE_TO_KEY if phrase in low}
    return [k for k in _OBLIGATION_ORDER if k in keys]


def build_catalog_data(catalog_path: str | Path | None = None) -> dict:
    checks = load_catalog(catalog_path)["checks"]
    return {"checks": {c["id"]: {"dec": c["dec"]} for c in checks}}


def build_obligations(catalog_path: str | Path | None = None) -> dict:
    checks = load_catalog(catalog_path)["checks"]
    obligations: dict[str, list[str]] = {}
    for check in checks:
        keys = obligations_for(check.get("art", ""))
        if keys:
            obligations[check["id"]] = keys
    return {"obligations": obligations}


def render_catalog_json(catalog_path: str | Path | None = None) -> str:
    return json.dumps(build_catalog_data(catalog_path), indent=2, sort_keys=True) + "\n"


def render_obligations_json(catalog_path: str | Path | None = None) -> str:
    return json.dumps(build_obligations(catalog_path), indent=2, sort_keys=True) + "\n"


def main() -> int:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    (_DATA_DIR / "catalog.json").write_text(render_catalog_json(), encoding="utf-8")
    (_DATA_DIR / "obligations.json").write_text(render_obligations_json(), encoding="utf-8")
    data = build_obligations()
    print(f"wrote policy/data/catalog.json and obligations.json "
          f"({len(data['obligations'])} checks with obligations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
