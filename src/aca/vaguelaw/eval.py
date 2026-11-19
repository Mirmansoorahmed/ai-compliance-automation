"""Eval harness for the vague-law classifier (Phase 5b).

Scores a labelled set of (state, question_id, expected_yes) cases through a
backend and reports accuracy, expected calibration error (ECE), and the ASK rate
(the share routed to a human). With the FakeBackend or the offline hashed
LocalBackend these are a SMOKE signal only; the real accuracy/ECE on the trained
model is **to be measured by the owner**.

Case file shape (eval/vaguelaw/*.yaml):
    id: vl-art22-pos-01
    question_id: GDPR-22
    state: "The model alone approves or rejects the loan ..."
    expect_yes: true
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from aca.register.yamlio import load_yaml
from aca.vaguelaw.backend import DecisionBackend
from aca.vaguelaw.classify import ASK, classify
from aca.vaguelaw.questions import load_questions

_CASES_DIR = Path(__file__).resolve().parents[3] / "eval" / "vaguelaw"

SMOKE_NOTE = ("smoke only (FakeBackend or offline hashed LocalBackend); real accuracy/ECE "
              "to be measured by the owner with the trained model")


@dataclass
class EvalResult:
    n: int
    accuracy: float | None
    ece: float | None
    ask_rate: float | None
    by_question: dict = field(default_factory=dict)
    note: str = SMOKE_NOTE


def load_cases(cases_dir: Path | None = None) -> list[dict]:
    base = cases_dir or _CASES_DIR
    if not base.exists():
        return []
    return [load_yaml(p) for p in sorted(base.glob("*.yaml"))]


def _ece(pairs: list[tuple[float, bool]], *, bins: int = 10) -> float | None:
    """Expected calibration error over p(yes) vs the correct label."""
    if not pairs:
        return None
    total = len(pairs)
    err = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        bucket = [(p, y) for p, y in pairs if (p > lo or (b == 0 and p == 0.0)) and p <= hi]
        if not bucket:
            continue
        conf = sum(p for p, _ in bucket) / len(bucket)
        acc = sum(1 for _, y in bucket if y) / len(bucket)
        err += (len(bucket) / total) * abs(conf - acc)
    return round(err, 4)


def evaluate(backend: DecisionBackend, *, cases_dir: Path | None = None) -> EvalResult:
    cases = load_cases(cases_dir)
    questions = {q.id: q for q in load_questions()}
    if not cases:
        return EvalResult(n=0, accuracy=None, ece=None, ask_rate=None)

    correct = 0
    scored = 0
    asks = 0
    cal_pairs: list[tuple[float, bool]] = []
    by_q: dict = {}

    for case in cases:
        qid = case["question_id"]
        q = questions.get(qid)
        if q is None:
            continue
        expect = bool(case["expect_yes"])
        routing = classify(case["state"], [q], backend)[0]
        qstat = by_q.setdefault(qid, {"n": 0, "correct": 0, "ask": 0})
        qstat["n"] += 1
        # p(yes) for calibration (routing carries it).
        cal_pairs.append((routing.p_yes, expect))
        if routing.route == ASK:
            asks += 1
            qstat["ask"] += 1
            continue  # ASK is neither right nor wrong; excluded from accuracy
        scored += 1
        predicted_yes = routing.route == "ACT"
        if predicted_yes == expect:
            correct += 1
            qstat["correct"] += 1

    accuracy = round(correct / scored, 4) if scored else None
    ask_rate = round(asks / len(cases), 4) if cases else None
    return EvalResult(
        n=len(cases),
        accuracy=accuracy,
        ece=_ece(cal_pairs),
        ask_rate=ask_rate,
        by_question=by_q,
    )
