"""Adapter interface for the Semantic Guard (R4.1).

One protocol, several backends:
    local_embeddings  (required)
    prompt_shields    (optional, hybrid)   -- Phase 10
    lakera            (stub only in v1)     -- Phase 10
    aws_placeholder   (unused slot)         -- Phase 10

Every adapter implements ``detect(event) -> list[dict]`` returning labels in the
schema in ``aca.guard.labels.schema``. An adapter never returns a verdict.
"""

from __future__ import annotations

from typing import Protocol

from aca.guard.event import Event


class Adapter(Protocol):
    name: str

    def detect(self, event: Event) -> list[dict]:
        """Return labels (possibly empty). Never a verdict."""
        ...
