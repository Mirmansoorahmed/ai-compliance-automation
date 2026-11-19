"""Enable ``python -m guardrails_mcp`` (runs the stdio MCP server)."""

from guardrails_mcp.server import main

if __name__ == "__main__":
    raise SystemExit(main())
