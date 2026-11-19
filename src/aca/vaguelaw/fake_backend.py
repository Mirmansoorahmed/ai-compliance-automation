"""Deterministic DecisionBackend for tests and demos (no model).

Answers each question from simple, explicit keyword signals in the state, so a
test can assert an exact p(yes) without any embedding model or network. It is
NOT a classifier — it exists so the routing logic (act / ASK) can be tested
deterministically. Each question may carry a scripted answer via
``script={question_id: p_yes}`` for full control.
"""

from __future__ import annotations

from aca.vaguelaw.backend import Answer, Question


class FakeBackend:
    name = "fake"

    def __init__(self, *, script: dict | None = None, default_p: float = 0.5):
        # script: question_id -> forced p_yes.
        self._script = dict(script or {})
        self._default_p = default_p

    def decide(self, state: str, questions: list[Question]) -> list[Answer]:
        low = state.lower()
        answers: list[Answer] = []
        for q in questions:
            if q.id in self._script:
                p = float(self._script[q.id])
                rationale = "scripted"
            else:
                # A trivially explicit signal: count positive vs negative cue words.
                pos_hits = sum(1 for cue in q.positives if _cue(cue) in low)
                neg_hits = sum(1 for cue in q.negatives if _cue(cue) in low)
                if pos_hits == 0 and neg_hits == 0:
                    p = self._default_p
                    rationale = "no cue matched (default)"
                else:
                    p = round((pos_hits + 0.5) / (pos_hits + neg_hits + 1.0), 4)
                    rationale = f"cue hits pos={pos_hits} neg={neg_hits}"
            answers.append(Answer(
                question_id=q.id, answer=p >= 0.5, p_yes=p,
                backend=self.name, rationale=rationale,
            ))
        return answers


def _cue(text: str) -> str:
    # Use the first few words of an exemplar as a deterministic cue substring.
    return " ".join(text.lower().split()[:3])
