"""A thin representation of the Agent Trust Gateway → Semantic Guard contract.

The real gateway is external and unchanged. ``GatewayLink`` models the slow-path
call it makes: label the tool call with the Guard, apply the ``compliance.tier``
decision (deny / four-eyes / ask / allow), and emit a redacted trace record. An
integration test uses this to show a social-scoring tool call being denied at
the gateway, with a trace record — the same contract the external gateway uses.

Privacy: the trace record carries labels and the tier only, never the raw tool
argument text (the Guard API already drops raw text; this keeps the same rule).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from aca.guard.event import Event
from aca.policy.decide import PolicyData, decide, load_policy_data


@dataclass(frozen=True)
class GatewayDecision:
    tier: str                 # deny | four-eyes | ask | allow
    allowed: bool             # False when tier == deny
    labels: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class TraceRecord:
    ts: float
    tool: str
    tier: str
    allowed: bool
    concept_ids: list[str]
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "ts": self.ts, "tool": self.tool, "tier": self.tier,
            "allowed": self.allowed, "concept_ids": self.concept_ids, "note": self.note,
        }


class GatewayLink:
    """Model of the gateway's slow-path call to the Guard (external gw unchanged)."""

    def __init__(self, adapter, *, policy: PolicyData | None = None):
        # ``adapter`` is a Guard label adapter exposing detect(Event) -> [label].
        self._adapter = adapter
        self._policy = policy or load_policy_data()

    def check_tool_call(self, *, tool: str, text: str, language: str | None = None) -> GatewayDecision:
        labels = self._adapter.detect(Event(text=text, language=language))
        tier = decide(labels, self._policy)
        return GatewayDecision(tier=tier, allowed=tier != "deny", labels=labels)

    def trace(self, tool: str, decision: GatewayDecision, *, note: str = "") -> TraceRecord:
        concept_ids = sorted({l.get("concept_id") for l in decision.labels if l.get("concept_id")})
        return TraceRecord(
            ts=time.time(), tool=tool, tier=decision.tier,
            allowed=decision.allowed, concept_ids=concept_ids, note=note,
        )
