"""Privacy-preserving redaction helpers for evidence (R10.2, R10.3).

- ``subject_pseudonym`` turns a clear subject id into a stable, salted pseudonym
  so the same subject is correlatable across spans without exposing identity.
- ``redact_args`` reduces tool arguments to key names, a count, and the SHA-256
  of each value — never the raw value. Raw prompt/argument bodies are never
  placed in a span.

The salt defaults to a fixed lab value so demo spans are reproducible. In a real
deployment it would come from config/secret; a rotating salt breaks long-term
re-identification, which is the point.
"""

from __future__ import annotations

import hashlib

DEFAULT_SALT = "aca-lab-pseudonym-salt"

# Fields that must never appear in a span (clear identity / raw content).
FORBIDDEN_SPAN_FIELDS = frozenset(
    {"agent.id", "agent_id", "role", "department", "prompt", "prompt_body", "text", "args_raw"}
)


def _sha256_hex(value: str, *, salt: str = "") -> str:
    return hashlib.sha256((salt + value).encode("utf-8")).hexdigest()


def subject_pseudonym(subject_id: str, *, salt: str = DEFAULT_SALT) -> str:
    """Stable, salted pseudonym for a subject. Prefixed for readability."""
    if not subject_id:
        return "subj-anon"
    return "subj-" + _sha256_hex(subject_id, salt=salt)[:16]


def redact_args(args: dict | None) -> dict:
    """Reduce args to {names, count, hashes} — key names, count, SHA-256 only.

    The raw values never leave this function. Hashes let a reviewer confirm two
    decisions saw the same argument value without seeing the value.
    """
    args = args or {}
    names = sorted(str(k) for k in args.keys())
    hashes = {name: _sha256_hex(_stringify(args[name])) for name in names}
    return {"names": names, "count": len(names), "hashes": hashes}


def _stringify(value) -> str:
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def assert_no_forbidden_fields(attributes: dict) -> None:
    """Raise if a span carries a clear-identity or raw-content field (R10.2/R10.3)."""
    bad = FORBIDDEN_SPAN_FIELDS.intersection(attributes.keys())
    if bad:
        raise ValueError(f"span carries forbidden field(s): {sorted(bad)}")
