"""Minimal MCP server (JSON-RPC 2.0 over stdio) with a `compliance_check` tool.

Dependency-free: implements just enough of MCP for an agent to discover and call
the tool — ``initialize``, ``tools/list``, ``tools/call``. The tool runs the
same decision engine as POST /v1/check in-process (offline hashed embedder), so
no service needs to be running.

``compliance_check`` arguments:
    { "event": "prompt" | "tool" | "diff",   (default "prompt")
      "text":  "<prompt text or shell command>",
      "diff":  "<new file content, for a write>",
      "use_case": { ... } | null }            (inline use-case.yaml dict)

Result content is a JSON object: {decision, check_ids, reasons, obligations,
missing_artefacts}.
"""

from __future__ import annotations

import json
import sys

from aca.check.service import CheckService
from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.embeddings import build_embedder
from aca.guard.service import SemanticGuard

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "guardrails-mcp"
SERVER_VERSION = "0.1.0"

_TOOL = {
    "name": "compliance_check",
    "description": (
        "Check an action (prompt, tool call, or file diff) against the EU AI "
        "compliance policy. Returns BLOCK/ASK/WARN/ALLOW with the rules that "
        "fired, their legal sources, and the obligations required. Call this "
        "before acting on anything that might be a regulated AI use."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "event": {"type": "string", "enum": ["prompt", "tool", "diff"], "default": "prompt"},
            "text": {"type": "string", "description": "prompt text, or a shell command for a tool event"},
            "diff": {"type": "string", "description": "new file content for a write/diff event"},
            "use_case": {"type": ["object", "null"], "description": "inline use-case.yaml declaration"},
        },
        "required": [],
    },
}


def build_service() -> CheckService:
    embedder = build_embedder(allow_hashed_fallback=True, dim=256)
    guard = SemanticGuard(adapters=[LocalEmbeddingsAdapter(embedder=embedder, dim=256)])
    return CheckService(guard=guard)


class ComplianceServer:
    def __init__(self, *, service: CheckService | None = None):
        self._service = service or build_service()

    def compliance_check(self, args: dict) -> dict:
        payload = {
            "event": args.get("event", "prompt"),
            "text": args.get("text", "") or "",
            "diff": args.get("diff", "") or "",
            "tool": "mcp",
        }
        uc = args.get("use_case")
        if isinstance(uc, dict):
            payload["use_case"] = uc
        return self._service.check(payload)

    def handle(self, request: dict) -> dict | None:
        method = request.get("method")
        req_id = request.get("id")

        if method == "initialize":
            return _result(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            })
        if method == "notifications/initialized":
            return None  # notification, no response
        if method == "tools/list":
            return _result(req_id, {"tools": [_TOOL]})
        if method == "tools/call":
            params = request.get("params") or {}
            name = params.get("name")
            if name != "compliance_check":
                return _error(req_id, -32602, f"unknown tool {name!r}")
            args = params.get("arguments") or {}
            decision = self.compliance_check(args)
            return _result(req_id, {
                "content": [{"type": "text", "text": json.dumps(decision)}],
                "structuredContent": decision,
                "isError": decision.get("decision") == "BLOCK",
            })
        if req_id is None:
            return None  # unknown notification
        return _error(req_id, -32601, f"method not found: {method}")


def _result(req_id, result) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code, message) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def serve(stdin=None, stdout=None) -> int:  # pragma: no cover - stdio loop
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    server = ComplianceServer()
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = server.handle(request)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
    return 0


def main() -> int:  # pragma: no cover
    return serve()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
