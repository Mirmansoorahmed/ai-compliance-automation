"""Vague-law classifier (Phase 5b).

Answers the open legal questions the catalog leaves to judgement — the Art. 6(3)
Annex III exception, GDPR Art. 22 solely-automated decisions, the Art. 50
transparency duty, and similar — as typed yes/no answers with a probability.

A pluggable ``DecisionBackend`` produces the answers:
  - ``LocalBackend``  — open-source, lazy-loaded MiniLM similarity (hashed
                        fallback offline). The default.
  - ``FakeBackend``   — deterministic, for tests and demos. No model.
  - ``JevBackend``    — optional closed vendor API (TypeSafe ``jev-1``), OFF by
                        default, operator's own key, synthetic data only, flagged
                        as an Art. 44 transfer + vendor risk. Never used in tests
                        or the default demo.

The decision layer maps a confident act-answer to the question's catalog
decision; low confidence routes to ASK (a human).
"""

from __future__ import annotations

from aca.vaguelaw.backend import Answer, DecisionBackend, Question
from aca.vaguelaw.fake_backend import FakeBackend
from aca.vaguelaw.local_backend import LocalBackend

__all__ = ["Answer", "DecisionBackend", "Question", "FakeBackend", "LocalBackend"]
