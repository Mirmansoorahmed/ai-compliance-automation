"""Runtime link to the Agent Trust Gateway (Phase 6).

The Agent Trust Gateway is a SEPARATE repository and is unchanged. It is the
runtime policy-enforcement point (PEP): on its slow path it calls the Semantic
Guard's ``POST /v1/labels`` with tool metadata and in-memory classification
text, then OPA (``compliance.tier``) takes the final allow / ask / deny.

This package does not modify the gateway. It provides a thin client + trace
helper that represents that integration contract, so an integration test can
exercise "gateway consults the Guard, OPA denies a tool call, a trace record is
emitted" without the external service — using the real Guard label + tier
decision in-process.
"""

from __future__ import annotations

from aca.runtime.gateway_link import GatewayDecision, GatewayLink, TraceRecord

__all__ = ["GatewayDecision", "GatewayLink", "TraceRecord"]
