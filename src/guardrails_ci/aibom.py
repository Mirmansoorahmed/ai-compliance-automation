"""Build a minimal CycloneDX-style AI-BOM for the repo.

Lists the AI/ML components the repo *declares* — the embedding model, the
hashed-fallback embedder, and the Python dependencies in pyproject.toml — as
CycloneDX 1.5 ``components``. Every component carries a ``provenance`` property
marking whether each value is ``declared`` (read from pyproject / source) or
``guessed`` (a reasonable default the repo does not state), so a reader never
mistakes an inference for a fact.

Dependency-free: pyproject is parsed with a tiny reader for the two arrays the
BOM needs (dependencies and the ``embeddings`` extra). This is a software
inventory, not a conformity claim.
"""

from __future__ import annotations

import re
from pathlib import Path

BOM_FORMAT = "CycloneDX"
SPEC_VERSION = "1.5"

_ROOT = Path(__file__).resolve().parents[2]
_PYPROJECT = _ROOT / "pyproject.toml"


def _extract_array(text: str, key: str) -> list[str]:
    """Pull a simple ``key = [ "a", "b" ]`` TOML array (single- or multi-line)."""
    m = re.search(rf"(?m)^{re.escape(key)}\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not m:
        return []
    body = m.group(1)
    return [item.strip().strip('"').strip("'") for item in re.findall(r"""["']([^"']+)["']""", body)]


def _read_declared(pyproject: Path) -> dict:
    text = pyproject.read_text(encoding="utf-8") if pyproject.is_file() else ""
    return {
        "dependencies": _extract_array(text, "dependencies"),
        "embeddings": _extract_array(text, "embeddings"),
    }


def _component(ctype: str, name: str, *, version: str = "", provenance: str = "declared",
               description: str = "", extra: dict | None = None) -> dict:
    comp = {
        "type": ctype,
        "name": name,
        "properties": [{"name": "guardrails:provenance", "value": provenance}],
    }
    if version:
        comp["version"] = version
    if description:
        comp["description"] = description
    if extra:
        comp.update(extra)
    return comp


def _split_req(req: str) -> tuple[str, str]:
    m = re.match(r"^\s*([A-Za-z0-9_.\-]+)\s*(.*)$", req)
    if not m:
        return req, ""
    return m.group(1), m.group(2).strip()


def build_aibom(pyproject: Path | None = None) -> dict:
    declared = _read_declared(pyproject or _PYPROJECT)
    components: list[dict] = []

    # The embedding model: named + pinned in the embeddings extra / docs.
    model_pin = next((r for r in declared["embeddings"] if r.lower().startswith("sentence-transformers")), "")
    _, model_spec = _split_req(model_pin) if model_pin else ("", "")
    # Strip a leading "==" so the version is a bare value (e.g. 3.0.1).
    model_ver = model_spec[2:].strip() if model_spec.startswith("==") else model_spec
    components.append(_component(
        "machine-learning-model",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        version=model_ver or "unpinned",
        # The library pin is declared; the specific model id is declared in docs
        # but not machine-read from a lockfile, so mark it guessed-from-docs.
        provenance="declared-in-docs",
        description="Local multilingual sentence embedding model (DE/EN, CPU). Used only when the 'embeddings' extra is installed.",
    ))

    # The deterministic fallback embedder lives in the repo source.
    components.append(_component(
        "machine-learning-model",
        "guardrails:HashedEmbedder",
        version="builtin",
        provenance="declared",
        description="Deterministic hashed-vector embedder used on the oss profile when no model is installed (reproducible, no download).",
    ))

    # Declared Python runtime dependencies (oss profile declares none).
    if declared["dependencies"]:
        for req in declared["dependencies"]:
            name, ver = _split_req(req)
            components.append(_component("library", name, version=ver or "unspecified", provenance="declared"))
    else:
        components.append(_component(
            "library", "python-stdlib-only", version="",
            provenance="declared",
            description="The oss profile declares no third-party runtime dependencies (standard library only).",
        ))

    # Optional embeddings-extra libraries (declared but not installed on oss).
    for req in declared["embeddings"]:
        if req.lower().startswith("sentence-transformers"):
            continue  # already listed as the model library
        name, ver = _split_req(req)
        components.append(_component(
            "library", name, version=ver or "unspecified",
            provenance="declared",
            description="Optional dependency of the 'embeddings' extra; absent on the oss profile.",
        ))

    return {
        "bomFormat": BOM_FORMAT,
        "specVersion": SPEC_VERSION,
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "ai-semantic-guardrails-eu",
                "description": "EU AI compliance guardrails (Semantic Guard + OPA). Synthetic data only; not a conformity claim.",
            },
            "properties": [
                {"name": "guardrails:note",
                 "value": "Minimal AI-BOM. 'provenance' marks declared vs guessed-from-docs values. Not a complete SBOM."},
            ],
        },
        "components": components,
    }
