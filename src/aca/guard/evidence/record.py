"""Decision-record v1 and the evidence span it maps to (R10.1).

One span is emitted per decision. The field set is the platform
decision-record v1 contract (DESIGN.md §5.4). The record is OTel-shaped: it
carries a span name, a resource, and a flat attribute map, so it maps directly
onto an OpenTelemetry span when the OTel SDK is present (see emitter.py). The
oss profile needs no OTel install.

Required fields (DESIGN.md §5.4):
  ts, decision_id, bundle_revision, pep=semantic, subject_pseudonym, groups,
  site, resource, action, tier, allowed, reason_code, labels[], args
  (names/count/hashes only), latency_ms, approver_pseudonyms[]
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from aca.guard.evidence.redact import (
    assert_no_forbidden_fields,
    redact_args,
    subject_pseudonym,
)

DECISION_RECORD_VERSION = "decision-record/v1"
SPAN_NAME = "semantic_guard.decision"

# The PEP for every span this repo emits is the semantic slow path.
PEP = "semantic"

REQUIRED_FIELDS = (
    "ts",
    "decision_id",
    "bundle_revision",
    "pep",
    "subject_pseudonym",
    "groups",
    "site",
    "resource",
    "action",
    "tier",
    "allowed",
    "reason_code",
    "labels",
    "args",
    "latency_ms",
    "approver_pseudonyms",
)

# Tiers that are NOT an allow. `allowed` is derived from the tier.
_NON_ALLOW = frozenset({"deny", "four-eyes", "ask"})


@dataclass(frozen=True)
class DecisionRecord:
    attributes: dict
    span_name: str = SPAN_NAME

    @property
    def decision_id(self) -> str:
        return self.attributes["decision_id"]

    def missing_fields(self) -> list[str]:
        return [f for f in REQUIRED_FIELDS if f not in self.attributes]


def build_decision_record(
    *,
    tier: str,
    subject_id: str,
    resource: str,
    action: str,
    labels: list[dict],
    bundle_revision: str,
    groups: list[str] | None = None,
    site: str | None = None,
    reason_code: str | None = None,
    args: dict | None = None,
    latency_ms: float | None = None,
    approver_ids: list[str] | None = None,
    salt: str | None = None,
    now: float | None = None,
    decision_id: str | None = None,
) -> DecisionRecord:
    """Build a privacy-preserving decision record for one decision.

    ``allowed`` is derived from the tier. The subject and approvers are
    pseudonymised. ``args`` are reduced to names/count/hashes. The result is
    checked to carry no forbidden clear-identity or raw-content field.
    """
    kwargs = {"salt": salt} if salt is not None else {}
    attributes = {
        "schema": DECISION_RECORD_VERSION,
        "ts": now if now is not None else time.time(),
        "decision_id": decision_id or str(uuid.uuid4()),
        "bundle_revision": bundle_revision,
        "pep": PEP,
        "subject_pseudonym": subject_pseudonym(subject_id, **kwargs),
        "groups": list(groups or []),
        "site": site,
        "resource": resource,
        "action": action,
        "tier": tier,
        "allowed": tier not in _NON_ALLOW,
        "reason_code": reason_code or f"tier:{tier}",
        "labels": labels,
        "args": redact_args(args),
        "latency_ms": latency_ms,
        "approver_pseudonyms": [subject_pseudonym(a, **kwargs) for a in (approver_ids or [])],
    }
    assert_no_forbidden_fields(attributes)
    return DecisionRecord(attributes=attributes)
