"""Find and load the repo's .guardrails/use-case.yaml for the CI gate.

Reuses the dependency-free YAML reader from the hook package so the CI gate has
no PyYAML dependency on the oss profile. Returns the parsed dict or None.
"""

from __future__ import annotations

from pathlib import Path

from guardrails_hook.yamlmini import load_yaml_file

DEFAULT_REL_PATH = Path(".guardrails") / "use-case.yaml"


def find_use_case(repo: str | Path = ".", *, explicit: str | Path | None = None) -> Path | None:
    if explicit is not None:
        p = Path(explicit)
        return p if p.is_file() else None
    p = Path(repo) / DEFAULT_REL_PATH
    return p if p.is_file() else None


def load_use_case(repo: str | Path = ".", *, explicit: str | Path | None = None) -> dict | None:
    path = find_use_case(repo, explicit=explicit)
    if path is None:
        return None
    try:
        doc = load_yaml_file(path)
    except Exception:
        return None
    return doc if isinstance(doc, dict) else None
