"""Phase 6 — the MCP compliance_check server (JSON-RPC handlers)."""

import json

import pytest

from guardrails_mcp.server import ComplianceServer


@pytest.fixture(scope="module")
def server():
    return ComplianceServer()


def test_initialize(server):
    resp = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert resp["result"]["serverInfo"]["name"] == "guardrails-mcp"
    assert "protocolVersion" in resp["result"]


def test_tools_list_exposes_compliance_check(server):
    resp = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in resp["result"]["tools"]]
    assert names == ["compliance_check"]


def test_initialized_notification_has_no_response(server):
    resp = server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert resp is None


def test_compliance_check_social_scoring_blocks(server):
    resp = server.handle({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "compliance_check", "arguments": {
            "event": "prompt",
            "text": ("Join badge logs, Slack activity and canteen data per employee into a "
                     "reliability index and drop the bottom 10% from the bonus pool."),
        }},
    })
    structured = resp["result"]["structuredContent"]
    assert structured["decision"] == "BLOCK"
    assert resp["result"]["isError"] is True
    assert "AIA-5-1-c" in structured["check_ids"]
    # The text content is valid JSON mirroring the decision.
    assert json.loads(resp["result"]["content"][0]["text"])["decision"] == "BLOCK"


def test_compliance_check_fraud_allows(server):
    resp = server.handle({
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "compliance_check", "arguments": {
            "event": "prompt",
            "text": "Compute a fraud risk score on card transactions and flag the riskiest for manual review.",
        }},
    })
    structured = resp["result"]["structuredContent"]
    assert structured["decision"] == "ALLOW"
    assert resp["result"]["isError"] is False


def test_compliance_check_secret_diff_blocks(server):
    resp = server.handle({
        "jsonrpc": "2.0", "id": 5, "method": "tools/call",
        "params": {"name": "compliance_check", "arguments": {
            "event": "diff",
            "diff": 'AWS_ACCESS_KEY_ID = "AKIAXXXXXXXXXXXXXXXX"',
        }},
    })
    structured = resp["result"]["structuredContent"]
    assert structured["decision"] == "BLOCK"
    assert "SEC-SECRETS" in structured["check_ids"]


def test_unknown_tool_errors(server):
    resp = server.handle({
        "jsonrpc": "2.0", "id": 6, "method": "tools/call",
        "params": {"name": "nope", "arguments": {}},
    })
    assert "error" in resp


def test_unknown_method_errors(server):
    resp = server.handle({"jsonrpc": "2.0", "id": 7, "method": "bogus/method"})
    assert resp["error"]["code"] == -32601
