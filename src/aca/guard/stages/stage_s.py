"""Stage S — session context (R3.7).

A rolling, TTL-bounded, pseudonymised store of *labels only*. It never stores
raw prompt text. It lets multi-turn "salami" attacks be seen: a sequence of
individually-weak turns whose labels accumulate.

Privacy by default: the key is a subject pseudonym, entries carry concept_id,
elements_met, confidence and a timestamp — no prompt bodies, no clear identity.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SessionLabel:
    concept_id: str
    elements_met: tuple[str, ...]
    confidence: float
    ts: float


@dataclass
class SessionContext:
    ttl_seconds: float = 900.0  # 15 minutes
    max_per_subject: int = 50
    _store: dict[str, deque] = field(default_factory=lambda: defaultdict(deque))

    def _now(self) -> float:
        return time.time()

    def _evict(self, subject_pseudonym: str, now: float) -> None:
        dq = self._store[subject_pseudonym]
        while dq and (now - dq[0].ts) > self.ttl_seconds:
            dq.popleft()
        while len(dq) > self.max_per_subject:
            dq.popleft()

    def add(self, subject_pseudonym: str, label: dict, *, now: float | None = None) -> None:
        """Record a label (labels only; raw text is rejected)."""
        forbidden = {"text", "prompt", "prompt_body", "args_raw"}
        if forbidden.intersection(label.keys()):
            raise ValueError("session context stores labels only, not raw text")
        now = now if now is not None else self._now()
        dq = self._store[subject_pseudonym]
        dq.append(
            SessionLabel(
                concept_id=label.get("concept_id", ""),
                elements_met=tuple(label.get("elements_met", [])),
                confidence=float(label.get("confidence", 0.0)),
                ts=now,
            )
        )
        self._evict(subject_pseudonym, now)

    def summary(self, subject_pseudonym: str, *, now: float | None = None) -> list[dict]:
        """Return the non-expired labels for a subject (for stage-1/OPA input)."""
        now = now if now is not None else self._now()
        self._evict(subject_pseudonym, now)
        return [
            {
                "concept_id": sl.concept_id,
                "elements_met": list(sl.elements_met),
                "confidence": sl.confidence,
            }
            for sl in self._store[subject_pseudonym]
        ]

    def accumulated_elements(self, subject_pseudonym: str, concept_id: str, *, now: float | None = None) -> set[str]:
        """Union of elements seen for a concept across the live session window."""
        now = now if now is not None else self._now()
        self._evict(subject_pseudonym, now)
        acc: set[str] = set()
        for sl in self._store[subject_pseudonym]:
            if sl.concept_id == concept_id:
                acc.update(sl.elements_met)
        return acc
