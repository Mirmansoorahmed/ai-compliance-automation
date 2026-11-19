"""Resolve the use-case.yaml the hook attaches to the /v1/check call.

Order: env GUARDRAILS_USE_CASE (a path), else <repo>/.guardrails/use-case.yaml.
Parsed with a tiny stdlib YAML reader (no PyYAML needed on the dev machine).
Returns the parsed dict, or None if absent/unreadable (never raises).
"""

from __future__ import annotations

import os
from pathlib import Path

from guardrails_hook.yamlmini import load_yaml_file


def resolve_use_case(repo: str | None) -> dict | None:
    candidates: list[Path] = []
    env_path = os.environ.get("GUARDRAILS_USE_CASE")
    if env_path:
        candidates.append(Path(env_path))
    if repo:
        candidates.append(Path(repo) / ".guardrails" / "use-case.yaml")
    # Also the current working directory as a fallback.
    candidates.append(Path(".guardrails") / "use-case.yaml")

    for path in candidates:
        try:
            if path.is_file():
                doc = load_yaml_file(path)
                if isinstance(doc, dict):
                    return doc
        except Exception:
            continue
    return None
