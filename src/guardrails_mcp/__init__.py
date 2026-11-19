"""MCP server exposing a `compliance_check` tool (Phase 6).

A minimal Model Context Protocol server over stdio (JSON-RPC 2.0), dependency-
free. It exposes one tool, ``compliance_check``, that runs the same /v1/check
decision engine in-process and returns the decision, rules and obligations, so
an agent (Codex, a Copilot extension, any MCP client) can ask for a compliance
decision before it acts — the enforcement path for tools without a blocking
hook.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
