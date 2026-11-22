"""Local, offline secret scan for the hook (catalog check SEC-SECRETS -> BLOCK).

A compact, dependency-free copy of the high-signal patterns so the hook can
block a secret write even when the policy service is unreachable. The fuller
scanner lives in ``aca.check.secrets`` (and gitleaks runs in CI); this must stay
a strict subset so the hook never allows a secret the service would block.
"""

from __future__ import annotations

import re

_PATTERNS = [
    re.compile(r"\b(?:api[_-]?key|secret|token|password|passwort)\b\s*[:=]\s*['\"]?[A-Za-z0-9/+_=-]{12,}", re.IGNORECASE),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"AccountKey=[A-Za-z0-9/+=]{20,}"),
    re.compile(r"\b[A-Za-z0-9_~.-]{3}8Q~[A-Za-z0-9_~.-]{30,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
]


def has_secret(text: str) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in _PATTERNS)
