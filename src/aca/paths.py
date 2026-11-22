"""Shared repository-path helpers.

One place resolves the repo root and the policy-data directory, so modules at
different nesting depths (the adapter under src/aca/guard/adapters/, the element
stage under src/aca/guard/stages/, the calibrators under src/aca/eval/) never
disagree on how many ``parents[...]`` to climb — a bug that previously pointed
the adapter at a non-existent ``src/policy/data`` and silently disabled the ASK
tier.

``ACA_POLICY_DATA_DIR`` overrides the policy-data directory (for tests or an
alternate deployment layout).
"""

from __future__ import annotations

import os
from pathlib import Path

# This file is src/aca/paths.py -> parents[0]=aca, [1]=src, [2]=<repo root>.
REPO_ROOT = Path(__file__).resolve().parents[2]

POLICY_DATA_DIR_ENV = "ACA_POLICY_DATA_DIR"


def repo_root() -> Path:
    return REPO_ROOT


def policy_data_dir() -> Path:
    """The signed policy-data directory (thresholds.json, element_margins.json, ...).

    Honours ``ACA_POLICY_DATA_DIR`` when set; otherwise ``<repo>/policy/data``.
    """
    override = os.environ.get(POLICY_DATA_DIR_ENV)
    if override:
        return Path(override)
    return REPO_ROOT / "policy" / "data"


def thresholds_path() -> Path:
    return policy_data_dir() / "thresholds.json"


def element_margins_path() -> Path:
    return policy_data_dir() / "element_margins.json"
