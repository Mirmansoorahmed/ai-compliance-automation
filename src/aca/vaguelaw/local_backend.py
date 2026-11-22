"""Local, open-source DecisionBackend (default).

Answers each question by embedding the ``state`` and comparing it to the
question's positive and negative exemplars (cosine similarity), then turning the
margin into a p(yes). Uses the trained MiniLM model when the ``embeddings``
extra is installed and falls back to the deterministic hashed embedder offline,
so it runs anywhere — reproducibly on the oss profile. Lazy-loaded: the embedder
is built on first use.

This is a similarity backend; an open NLI model could be slotted in behind the
same interface later. No closed vendor is contacted.
"""

from __future__ import annotations

from aca.guard.embeddings import build_embedder, cosine, resolve_embedder
from aca.vaguelaw.backend import Answer, Question


def _logistic(x: float, *, k: float = 6.0) -> float:
    # Map a similarity margin in roughly [-1, 1] to a probability in (0, 1).
    import math
    return 1.0 / (1.0 + math.exp(-k * x))


class LocalBackend:
    name = "local"

    def __init__(self, *, embedder=None, dim: int = 256, require_model: bool | None = None):
        self._embedder = embedder
        self._dim = dim
        self._require_model = require_model

    def _emb(self):
        if self._embedder is None:
            # Fix #4: shared loader. With require_model (or ACA_REQUIRE_MODEL=1)
            # this fails loudly rather than silently using the hashed fallback.
            self._embedder = resolve_embedder(require_model=self._require_model, dim=self._dim)
        return self._embedder

    def _p_yes(self, state_vec, q: Question) -> float:
        emb = self._emb()
        pos = [emb.embed(t) for t in q.positives] or [state_vec]
        neg = [emb.embed(t) for t in q.negatives] or []
        best_pos = max((cosine(state_vec, v) for v in pos), default=0.0)
        best_neg = max((cosine(state_vec, v) for v in neg), default=0.0)
        margin = best_pos - best_neg
        return round(_logistic(margin), 4)

    def decide(self, state: str, questions: list[Question]) -> list[Answer]:
        emb = self._emb()
        state_vec = emb.embed(state)
        answers: list[Answer] = []
        for q in questions:
            p = self._p_yes(state_vec, q)
            answers.append(Answer(
                question_id=q.id,
                answer=p >= 0.5,
                p_yes=p,
                backend=f"{self.name}:{emb.version}",
                rationale="similarity to positive vs negative exemplars",
            ))
        return answers
