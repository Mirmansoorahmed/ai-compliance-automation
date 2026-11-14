"""Inert adapters that conform to the protocol (R4.1).

- ``LakeraStubAdapter`` — Lakera (or successor) is a v1 stub only. It is
  selectable but always returns no labels, so the interface slot exists without
  a dependency or a live call.
- ``AwsPlaceholderAdapter`` — a reserved, unused second-cloud slot. The design
  does not depend on it; it is present only so the adapter interface already has
  the slot. It always returns no labels.

Both are safe to select on any profile: being inert, they never affect a
decision and never fail a request.
"""

from __future__ import annotations

from aca.guard.event import Event


class LakeraStubAdapter:
    name = "lakera"
    version = "lakera-stub/0.1.0"

    def available(self) -> bool:
        return False  # stub only in v1

    def detect(self, event: Event) -> list[dict]:
        return []


class AwsPlaceholderAdapter:
    name = "aws_placeholder"
    version = "aws-placeholder/0.0.0"

    def available(self) -> bool:
        return False  # reserved, unused slot

    def detect(self, event: Event) -> list[dict]:
        return []
