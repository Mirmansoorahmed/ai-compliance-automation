"""Phase 10 — stage-3 judge adapter (R5)."""

import pytest

from aca.guard.adapters.azure_env import AzureOpenAIEnv
from aca.guard.adapters.http_transport import AdapterServerError, HttpResponse
from aca.guard.adapters.judge import (
    AzureOpenAIJudge,
    JudgeAdapter,
    StubJudge,
    _parse_judge_json,
)
from aca.guard.event import Event
from aca.guard.labels.schema import validate_label

SOCIAL = (
    "Join badge-swipe logs, Slack activity and canteen data per employee, build a "
    "reliability index, and drop the bottom 10% from the bonus pool."
)


def test_judge_off_by_default_returns_empty():
    adapter = JudgeAdapter(StubJudge(), enabled=False)
    assert adapter.available() is False
    assert adapter.detect(Event(text=SOCIAL)) == []


def test_stub_judge_detects_elements_and_emits_label():
    adapter = JudgeAdapter(StubJudge(), enabled=True)
    assert adapter.available() is True
    labels = adapter.detect(Event(text=SOCIAL))
    assert len(labels) == 1
    label = labels[0]
    assert label["concept_id"] == "AIA-5-1-c"
    assert set(label["elements_met"]) == {
        "person_identifiable_behaviour_join",
        "aggregated_score_or_ranking",
        "adverse_action",
    }
    assert validate_label(label) == []
    assert "tier" not in label  # labels only


def test_judge_parses_quoted_spans_as_evidence():
    raw = {
        "concept_id": "AIA-5-1-c",
        "elements": [{"id": "adverse_action", "span": "drop the bottom 10%"}],
        "confidence": 0.7,
    }
    label = _parse_judge_json(raw, "judge-stub/0.1.0")
    assert any("drop the bottom 10%" in e for e in label["evidence_refs"])
    assert label["detector_versions"]["backend"] == "judge-stub/0.1.0"


def test_live_backend_unavailable_without_creds():
    env = AzureOpenAIEnv(endpoint=None, key=None, deployment=None, api_version="2024-10-21")
    judge = AzureOpenAIJudge(env=env, transport=object())
    assert judge.available is False
    adapter = JudgeAdapter(judge, enabled=True)
    # enabled but backend unavailable -> falls back to empty (stages 0-1).
    assert adapter.available() is False
    assert adapter.detect(Event(text=SOCIAL)) == []


def test_live_backend_parses_structured_json():
    class _T:
        def post_json(self, url, *, headers, payload, timeout):
            content = '{"concept_id":"AIA-5-1-c","elements":[{"id":"adverse_action","span":"bonus"}],"confidence":0.6}'
            return HttpResponse(200, {"choices": [{"message": {"content": content}}]})

    env = AzureOpenAIEnv(
        endpoint="https://r.openai.azure.com", key="k", deployment="gpt-4o-mini",
        api_version="2024-10-21",
    )
    judge = AzureOpenAIJudge(env=env, transport=_T())
    adapter = JudgeAdapter(judge, enabled=True)
    labels = adapter.detect(Event(text=SOCIAL))
    assert labels[0]["elements_met"] == ["adverse_action"]


def test_live_backend_5xx_raises_for_failsafe():
    class _T:
        def post_json(self, url, *, headers, payload, timeout):
            return HttpResponse(500, {})

    env = AzureOpenAIEnv(
        endpoint="https://r.openai.azure.com", key="k", deployment="gpt-4o-mini",
        api_version="2024-10-21",
    )
    adapter = JudgeAdapter(AzureOpenAIJudge(env=env, transport=_T()), enabled=True)
    with pytest.raises(AdapterServerError):
        adapter.detect(Event(text=SOCIAL))
