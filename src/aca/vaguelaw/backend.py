"""The DecisionBackend interface and the typed question/answer records.

A backend takes a free-text ``state`` (the use-case declaration + any code-
behaviour summary) and a set of ``Question``s, and returns one ``Answer`` per
question: a yes/no plus a probability in [0, 1] for "yes". The classifier layer
(decide.py) turns that into an act / ASK routing using each question's
``act_threshold`` and ``ask_below``.

Backends must be deterministic given the same inputs OR clearly mark themselves
non-deterministic (the closed vendor backend). Tests use the FakeBackend only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Question:
    id: str                      # catalog check id the question serves
    question: str
    act_label: str               # decision to apply when answered "yes" confidently
    act_threshold: float = 0.6   # p(yes) at/above this -> act on act_label
    ask_below: float = 0.6       # p(yes) below this (but not clearly "no") -> ASK
    positives: list[str] = field(default_factory=list)
    negatives: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Answer:
    question_id: str
    answer: bool                 # the yes/no the backend commits to
    p_yes: float                 # probability of "yes" in [0, 1]
    backend: str                 # which backend produced it
    rationale: str = ""

    @property
    def confidence(self) -> float:
        """Confidence in the committed answer (distance from 0.5, scaled)."""
        return round(abs(self.p_yes - 0.5) * 2.0, 4)


class DecisionBackend(Protocol):
    name: str

    def decide(self, state: str, questions: list[Question]) -> list[Answer]:
        ...
