"""Turn backend answers into a routing per question: ACT / NO / ASK.

For each question:
  - p(yes) >= act_threshold           -> ACT  (apply the question's act_label,
                                               e.g. BLOCK or ASK from the catalog)
  - p(yes) <  (1 - act_threshold)     -> NO   (the condition is confidently absent)
  - otherwise (uncertain, p in band)  -> ASK  (a human decides)

A single ``classify`` call runs the backend once over all questions and returns
one ``Routing`` each. Low confidence never silently resolves — it goes to ASK,
consistent with the Guard's fail-safe posture.
"""

from __future__ import annotations

from dataclasses import dataclass

from aca.vaguelaw.backend import Answer, DecisionBackend, Question

ACT = "ACT"
NO = "NO"
ASK = "ASK"


@dataclass(frozen=True)
class Routing:
    question_id: str
    route: str            # ACT | NO | ASK
    act_label: str        # the decision to apply if route == ACT
    p_yes: float
    confidence: float
    backend: str
    rationale: str = ""


def _route_for(q: Question, a: Answer) -> str:
    if a.p_yes >= q.act_threshold:
        return ACT
    if a.p_yes <= (1.0 - q.act_threshold):
        return NO
    return ASK


def classify(state: str, questions: list[Question], backend: DecisionBackend) -> list[Routing]:
    answers = backend.decide(state, questions)
    by_id = {a.question_id: a for a in answers}
    routings: list[Routing] = []
    for q in questions:
        a = by_id.get(q.id)
        if a is None:
            # No answer -> fail safe to ASK.
            routings.append(Routing(q.id, ASK, q.act_label, 0.5, 0.0, backend.name,
                                    "no answer from backend; routed to ASK"))
            continue
        route = _route_for(q, a)
        routings.append(Routing(
            question_id=q.id,
            route=route,
            act_label=q.act_label,
            p_yes=a.p_yes,
            confidence=a.confidence,
            backend=a.backend,
            rationale=a.rationale,
        ))
    return routings
