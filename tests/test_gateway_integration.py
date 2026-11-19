"""Phase 6 — integration with the (unchanged) Agent Trust Gateway contract.

The real gateway is external and unchanged. This exercises the contract it uses:
the gateway labels a tool call with the Semantic Guard, OPA (compliance.tier)
decides, and a social-scoring tool call is DENIED with a trace record. Offline
(hashed embedder); no external service.
"""

from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.embeddings import build_embedder
from aca.policy.decide import PolicyData, load_policy_data
from aca.runtime import GatewayLink

SOCIAL = ("Join badge logs, Slack activity and canteen data per employee into a "
          "reliability index and drop the bottom 10% from the bonus pool.")
FRAUD = "Compute a fraud risk score on card transactions and flag the riskiest for manual review."


def _adapter():
    return LocalEmbeddingsAdapter(embedder=build_embedder(allow_hashed_fallback=True, dim=256), dim=256)


def _policy_with_confirmed():
    # A confirmed prohibited pattern (a recorded human interpretation) makes a
    # full social-scoring match a hard deny at the gateway.
    base = load_policy_data()
    return PolicyData(thresholds=base.thresholds,
                      confirmed_prohibited_patterns=["AIA-5-1-c/joined-behaviour-adverse-action"])


def test_social_scoring_tool_call_denied_at_gateway():
    link = GatewayLink(_adapter(), policy=_policy_with_confirmed())
    decision = link.check_tool_call(tool="mcp__db__run", text=SOCIAL)
    assert decision.tier == "deny"
    assert decision.allowed is False
    trace = link.trace("mcp__db__run", decision, note="blocked at gateway")
    assert trace.allowed is False
    assert "AIA-5-1-c" in trace.concept_ids


def test_benign_tool_call_allowed_at_gateway():
    link = GatewayLink(_adapter(), policy=_policy_with_confirmed())
    decision = link.check_tool_call(tool="mcp__db__run", text=FRAUD)
    assert decision.allowed is True
    assert decision.tier in ("allow", "ask")


def test_trace_record_carries_no_raw_text():
    link = GatewayLink(_adapter(), policy=_policy_with_confirmed())
    decision = link.check_tool_call(tool="shell", text=SOCIAL)
    trace = link.trace("shell", decision)
    blob = str(trace.to_dict())
    assert "bonus pool" not in blob  # raw argument text is not in the trace
    assert "reliability index" not in blob
