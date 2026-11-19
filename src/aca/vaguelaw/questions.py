"""Load the vague-law question sets.

The questions are curated in policy/catalog/questions.yaml, derived from
catalog.yaml (the source of truth). This loader returns ``Question`` records.
Uses the project's YAML reader (PyYAML when present, the dependency-free reader
otherwise).
"""

from __future__ import annotations

from pathlib import Path

from aca.register.yamlio import load_yaml
from aca.vaguelaw.backend import Question

_QUESTIONS_PATH = Path(__file__).resolve().parents[3] / "policy" / "catalog" / "questions.yaml"


def load_questions(path: Path | None = None) -> list[Question]:
    data = load_yaml(path or _QUESTIONS_PATH)
    out: list[Question] = []
    for q in data.get("questions", []):
        out.append(Question(
            id=q["id"],
            question=q["question"],
            act_label=q.get("act_label", "ASK"),
            act_threshold=float(q.get("act_threshold", 0.6)),
            ask_below=float(q.get("ask_below", 0.6)),
            positives=list(q.get("positives", []) or []),
            negatives=list(q.get("negatives", []) or []),
        ))
    return out


def question_by_id(qid: str, path: Path | None = None) -> Question | None:
    for q in load_questions(path):
        if q.id == qid:
            return q
    return None
