"""Decision pipeline: Guard labels -> OPA decision -> evidence span.

Ties the pieces built in Phases 3-6 into one call. The Guard emits labels, the
policy (Python mirror of policy/tier.rego) decides the tier, and one evidence
span is recorded per decision. On a Guard failure the fail-safe tier applies and
is still recorded — never a silent allow for a risky/unknown tool class.

OPA is authoritative in production/CI; the Python mirror lets the demo and tests
run in-process without an OPA sidecar.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from aca.guard.evidence.emitter import EvidenceEmitter
from aca.guard.evidence.record import DecisionRecord
from aca.guard.event import Event
from aca.guard.failsafe.policy import failsafe_tier
from aca.guard.service import SemanticGuard
from aca.policy.decide import PolicyData, decide, load_policy_data


@dataclass
class DecisionPipeline:
    guard: SemanticGuard
    emitter: EvidenceEmitter
    policy_data: PolicyData
    bundle_revision: str = "oss-local"

    @classmethod
    def build(cls, guard: SemanticGuard, emitter: EvidenceEmitter, *, bundle_revision: str = "oss-local") -> "DecisionPipeline":
        return cls(guard=guard, emitter=emitter, policy_data=load_policy_data(), bundle_revision=bundle_revision)

    def decide(
        self,
        event: Event,
        *,
        subject_id: str,
        resource: str,
        action: str,
        groups: list[str] | None = None,
        site: str | None = None,
        args: dict | None = None,
        approver_ids: list[str] | None = None,
    ) -> DecisionRecord:
        start = time.perf_counter()
        tool_class = event.tool.get("class")

        try:
            labels, healthy = self.guard.label_with_health(event)
        except Exception:
            # Defensive: the Guard itself blew up, not just one adapter.
            labels, healthy = [], False

        if not healthy:
            # The Guard could not classify at all. Apply the fail-safe tier for
            # the tool class: risky/unknown -> ask, never a silent allow. The
            # deterministic gateway path is unaffected (handled by the gateway).
            tier = failsafe_tier(tool_class)
            reason = "guard_unavailable_failsafe"
            labels = []
        else:
            # Guard ran; OPA (mirror) decides from the labels it produced.
            tier = decide(labels, self.policy_data)
            reason = f"tier:{tier}"

        latency_ms = (time.perf_counter() - start) * 1000.0
        return self.emitter.emit(
            tier=tier,
            subject_id=subject_id,
            resource=resource,
            action=action,
            labels=labels,
            bundle_revision=self.bundle_revision,
            groups=groups,
            site=site,
            reason_code=reason,
            args=args,
            latency_ms=round(latency_ms, 3),
            approver_ids=approver_ids,
        )
