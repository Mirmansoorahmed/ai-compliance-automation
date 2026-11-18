"""Phase 5 — fail-safe behaviour tests (R8).

Covers the three failure paths — adapter absent, Guard timeout, Guard 5xx —
asserting risky tools degrade to `ask` and there is never a silent allow.
"""

import pytest

from aca.guard.event import Event
from aca.guard.failsafe.policy import (
    GuardUnavailable,
    failsafe_tier,
    is_silent_allow,
)
from aca.guard.service import SemanticGuard


def test_risky_class_degrades_to_ask():
    assert failsafe_tier("risky") == "ask"


def test_unknown_class_is_conservative_ask():
    assert failsafe_tier(None) == "ask"
    assert failsafe_tier("mystery") == "ask"


def test_log_only_may_fail_open():
    assert failsafe_tier("log-only") == "allow"


def test_no_silent_allow_for_risky():
    # A risky tool ending at allow during an outage is a bug.
    assert is_silent_allow("risky", "allow") is True
    assert is_silent_allow("risky", "ask") is False
    # log-only allow is acceptable, not a silent allow.
    assert is_silent_allow("log-only", "allow") is False


def _raising_adapter(exc):
    class _A:
        name = "boom"

        def detect(self, event):
            raise exc

    return _A()


def test_guard_skips_failing_adapter_but_keeps_others():
    # Timeout-style and 5xx-style failures both surface as exceptions from the
    # adapter; the Guard must skip them without raising.
    from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
    from aca.guard.embeddings import HashedEmbedder

    good = LocalEmbeddingsAdapter(embedder=HashedEmbedder(dim=128))
    guard = SemanticGuard(adapters=[_raising_adapter(TimeoutError("timeout")), good])
    labels = guard.label(Event(text="hello"))
    # The good adapter still produced a label; the failing one was skipped.
    assert any(l["concept_id"] == "AIA-5-1-c" for l in labels)


def test_guard_with_all_adapters_failing_returns_empty_not_error():
    guard = SemanticGuard(adapters=[_raising_adapter(RuntimeError("500"))])
    labels = guard.label(Event(text="hello"))
    assert labels == []
    # With no labels, OPA sees nothing to escalate; the gateway applies the
    # fail-safe tier for the tool class instead (never a silent allow).
    assert failsafe_tier("risky") == "ask"


def test_label_with_health_reports_unhealthy_when_all_adapters_fail():
    guard = SemanticGuard(adapters=[_raising_adapter(TimeoutError("t"))])
    labels, healthy = guard.label_with_health(Event(text="hello"))
    assert labels == []
    assert healthy is False


def test_label_with_health_is_healthy_when_one_adapter_succeeds():
    from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
    from aca.guard.embeddings import HashedEmbedder

    good = LocalEmbeddingsAdapter(embedder=HashedEmbedder(dim=128))
    guard = SemanticGuard(adapters=[_raising_adapter(RuntimeError("500")), good])
    labels, healthy = guard.label_with_health(Event(text="hello"))
    assert healthy is True
    assert labels  # the good adapter produced at least one label
