"""Deterministic secret scanner for tool/diff events (check SEC-SECRETS -> BLOCK).

Regexes for common key formats. This is a signal, not a legal judgement: a
match fires the SEC-SECRETS catalog check, which the catalog maps to BLOCK. It
is deliberately conservative and dependency-free (the oss profile ships no
gitleaks); CI runs gitleaks as the fuller scanner.
"""

from __future__ import annotations

import re

# Common secret formats (synthetic-data friendly, high-signal prefixes).
_PATTERNS = [
    # Generic "key/secret/token/password = <value>" assignments.
    (re.compile(r"\b(?:api[_-]?key|secret|token|password|passwort)\b\s*[:=]\s*['\"]?[A-Za-z0-9/+_=-]{12,}", re.IGNORECASE), "assignment"),
    # AWS access key id.
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws_access_key_id"),
    # Azure storage / shared key style (AccountKey=...).
    (re.compile(r"AccountKey=[A-Za-z0-9/+=]{20,}"), "azure_account_key"),
    # Azure AD client secret style and generic long base64 after 'key'.
    (re.compile(r"\b[A-Za-z0-9_~.-]{3}8Q~[A-Za-z0-9_~.-]{30,}\b"), "azure_client_secret"),
    # GitHub tokens.
    (re.compile(r"\bghp_[A-Za-z0-9]{36}\b"), "github_pat"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b"), "github_fine_grained_pat"),
    # OpenAI-style keys.
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "openai_key"),
    # Slack tokens.
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "slack_token"),
    # Private key blocks.
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"), "private_key"),
]


def scan_secrets(text: str) -> list[str]:
    """Return the kinds of secret found (empty if none)."""
    if not text:
        return []
    kinds: list[str] = []
    for pattern, kind in _PATTERNS:
        if pattern.search(text) and kind not in kinds:
            kinds.append(kind)
    return kinds


def has_secret(text: str) -> bool:
    return bool(scan_secrets(text))
