"""Phase 10 — lakera stub and aws_placeholder slot (R4.1)."""

from aca.guard.adapters.stubs import AwsPlaceholderAdapter, LakeraStubAdapter
from aca.guard.event import Event


def test_lakera_stub_is_inert_but_conforms():
    a = LakeraStubAdapter()
    assert a.name == "lakera"
    assert a.available() is False
    assert a.detect(Event(text="anything")) == []


def test_aws_placeholder_is_inert_but_conforms():
    a = AwsPlaceholderAdapter()
    assert a.name == "aws_placeholder"
    assert a.available() is False
    assert a.detect(Event(text="anything")) == []


def test_both_implement_detect_protocol():
    for a in (LakeraStubAdapter(), AwsPlaceholderAdapter()):
        result = a.detect(Event(text="x"))
        assert isinstance(result, list)
