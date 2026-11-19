"""guardrails-hook — the thin adapter that connects an AI coding tool's hook to
the compliance policy service (POST /v1/check).

It reads the tool's hook JSON from stdin, maps it to the normalised /v1/check
event, calls the service, and prints the decision in the format the tool
expects. It is deliberately small and dependency-free (standard library only),
fail-safe to ASK, and blocks a secret write even when the service is down.
"""

__version__ = "0.1.0"
