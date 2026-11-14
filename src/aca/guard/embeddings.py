"""Embedding backend for stage 1 (R3.3, and user constraint 3).

Two backends behind one interface:

- ``SentenceTransformerEmbedder`` — a small, CPU-only, multilingual
  sentence-transformers model. The default is pinned to
  ``sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`` (a MiniLM-class
  model that handles German and English), so stage 1 separates DE and EN
  exemplars with real semantics, not just character n-grams. The model name is
  recorded in the embedder ``version`` so every eval run says which backend
  produced it.
- ``HashedEmbedder`` — a deterministic hashed bag-of-character-ngrams vector,
  the fallback when the model cannot be loaded (e.g. CI / an offline sandbox).
  Reproducible: the same text always maps to the same vector.

``build_embedder`` prefers the real model and falls back to the hashed embedder
only when ``allow_hashed_fallback`` is set (the oss default). The fallback is a
baseline, not a trained-model result; runs record which backend was used so a
number is never mistaken for the other.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class Embedder(Protocol):
    name: str
    version: str

    def embed(self, text: str) -> list[float]:
        ...


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _char_ngrams(token: str, n: int = 3) -> list[str]:
    padded = f"#{token}#"
    if len(padded) <= n:
        return [padded]
    return [padded[i : i + n] for i in range(len(padded) - n + 1)]


class HashedEmbedder:
    """Deterministic, dependency-free embedding for reproducible CI."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self.name = "hashed"
        self.version = f"hashed/0.1.0:dim={dim}"

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = _TOKEN_RE.findall(text.lower())
        for token in tokens:
            for gram in _char_ngrams(token):
                h = hashlib.sha256(gram.encode("utf-8")).digest()
                idx = int.from_bytes(h[:4], "big") % self.dim
                sign = 1.0 if h[4] & 1 else -1.0
                vec[idx] += sign
        return vec


# Pinned default model: multilingual MiniLM (handles DE + EN), small and CPU-OK.
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class SentenceTransformerEmbedder:  # pragma: no cover - requires the model
    """Wraps a small CPU-only sentence-transformers model when available."""

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._model = SentenceTransformer(model, device="cpu")
        self.name = "sentence-transformers"
        self.version = f"st:{model}"

    def embed(self, text: str) -> list[float]:
        return [float(x) for x in self._model.encode(text, normalize_embeddings=True)]


def build_embedder(
    model: str = DEFAULT_MODEL,
    *,
    allow_hashed_fallback: bool = True,
    dim: int = 256,
) -> Embedder:
    """Return the real model if available, else the hashed fallback.

    Raises if the model is unavailable and the fallback is disabled, so a
    profile that *requires* the real model fails loudly rather than silently
    degrading. The returned embedder's ``version`` records which backend was
    chosen, so a committed eval run always states its provenance.
    """
    try:  # pragma: no cover - exercised only when the package is installed
        return SentenceTransformerEmbedder(model)
    except Exception:
        if not allow_hashed_fallback:
            raise RuntimeError(
                f"embedding model {model!r} unavailable and hashed fallback disabled"
            )
        return HashedEmbedder(dim=dim)
