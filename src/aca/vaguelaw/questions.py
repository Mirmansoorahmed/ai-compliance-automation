"""Load the vague-law question sets.

The questions are curated in config/vaguelaw/questions.yaml, derived from
catalog.yaml (the source of truth). They live under config/ rather than policy/
so OPA does not load them as bundle data (OPA treats every .yaml under policy/
as data and would hit a merge conflict on data.catalog.version). This loader
returns ``Question`` records, using the project's YAML reader (PyYAML when
present, the dependency-free reader otherwise).
"""

from __future__ import annotations

from pathlib import Path

from aca.register.yamlio import load_yaml
from aca.vaguelaw.backend import Question

_QUESTIONS_PATH = Path(__file__).resolve().parents[3] / "config" / "vaguelaw" / "questions.yaml"


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
