"""Fail-safe behaviour on Guard failure (R8).

When the Semantic Guard times out or errors on the slow path:

- the deterministic gateway path is unaffected (handled by the gateway; this
  module only decides the Guard-contribution fallback),
- tools in the ``risky`` class are forced to ``ask`` — never a silent allow,
- ``log-only`` classes may fail open (``allow``) and are logged,
- any other/unknown class is treated conservatively as ``risky`` and asked.

This is a safety control: the worst automatic outcome for an uninterpreted or
unavailable path is "pause and ask a human".
"""

from __future__ import annotations

# Tool classes and their fail behaviour. Documented here and in design.md §7.
FAIL_OPEN_CLASSES = frozenset({"log-only"})
FAIL_SAFE_CLASSES = frozenset({"risky", "sensitive", "write", "exfil"})


class GuardUnavailable(Exception):
    """Raised/handled when the Guard cannot produce labels (timeout or 5xx)."""


def failsafe_tier(tool_class: str | None) -> str:
    """Return the tier to apply when the Guard is unavailable.

    Never returns ``allow`` for a risky/unknown class; unknown classes are
    treated as risky by default so a mis-tagged tool cannot slip through.
    """
    if tool_class in FAIL_OPEN_CLASSES:
        return "allow"
    if tool_class in FAIL_SAFE_CLASSES:
        return "ask"
    # Unknown / untagged class -> conservative.
    return "ask"


def is_silent_allow(tool_class: str | None, tier: str) -> bool:
    """True if this would be a silent allow for a non-fail-open class (a bug)."""
    return tier == "allow" and tool_class not in FAIL_OPEN_CLASSES
