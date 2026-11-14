"""The event the Semantic Guard classifies.

An ``Event`` is the in-memory classification request: tool metadata, the text
needed to classify, an optional diff/artefact, and a session-label summary.
Raw text lives only in memory for the duration of the call; it is never
persisted by default (R3.7, R7.4, R10.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Event:
    # Free text to classify (prompt and/or tool-argument text). In memory only.
    text: str = ""
    # Tool metadata, e.g. {"name": ..., "class": "risky", "data_class": "pii"}.
    tool: dict = field(default_factory=dict)
    # Optional code/diff artefact for stage A.
    artefact: str = ""
    # Language hint ("de" | "en" | None). Detection also works without it.
    language: str | None = None
    # Session-label summary (labels only, no prompt text) for stage S context.
    session_labels: list[dict] = field(default_factory=list)
