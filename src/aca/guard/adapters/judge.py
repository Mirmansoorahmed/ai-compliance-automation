"""Stage-3 LLM judge adapter — Azure OpenAI / Foundry (R5).

OFF BY DEFAULT, even on the hybrid profile. When enabled and credentials are
present, the judge is asked, with a *pinned* rubric and a *pinned* model
deployment, to list which legal-concept elements are present and quote the
spans that support each. The structured JSON it returns is parsed into labels.

Safety:
- The judge emits labels (elements + confidence + quoted-span evidence), never a
  verdict. OPA still decides.
- Unavailable (no creds) or a live failure (timeout/401/429/5xx) -> the adapter
  returns ``[]`` (unavailable) or raises (live failure). Either way the result
  falls back to stages 0-1 and the pipeline never produces a silent allow
  (R5.3).
- ``StubJudge`` returns a canned structured response so the judge path is fully
  testable offline (R5.4).

The rubric is pinned in ``RUBRIC`` and versioned via ``ADAPTER_VERSION`` so a
model/prompt change is an explicit, reviewable edit.
"""

from __future__ import annotations

import json
from typing import Protocol

from aca.guard.adapters.azure_env import AzureOpenAIEnv, read_azure_openai_env
from aca.guard.adapters.http_transport import Transport, UrllibTransport, check_response
from aca.guard.event import Event
from aca.guard.labels.schema import Label

ADAPTER_VERSION = "judge/0.1.0"

# Pinned rubric. Changing it is a reviewed edit; the version string bumps with it.
RUBRIC = (
    "You are a compliance element detector, not a decision maker. For the concept "
    "AIA-5-1-c (social scoring of natural persons), decide which of these elements "
    "are present in the text and quote the exact span for each: "
    "person_identifiable_behaviour_join, aggregated_score_or_ranking, adverse_action. "
    "Return STRICT JSON only: "
    '{"concept_id":"AIA-5-1-c","elements":[{"id":"...","span":"..."}],"confidence":0.0}. '
    "Do not output an allow/deny decision."
)


class JudgeBackend(Protocol):
    version: str

    def complete_json(self, system: str, user: str) -> dict:
        ...


class StubJudge:
    """Offline stub: deterministic structured response for tests (R5.4)."""

    version = "judge-stub/0.1.0"

    def __init__(self, response: dict | None = None) -> None:
        self._response = response

    def complete_json(self, system: str, user: str) -> dict:
        if self._response is not None:
            return self._response
        low = user.lower()
        elements = []
        if any(w in low for w in ("badge", "slack", "canteen", "attendance", "zutritt", "kantine")):
            elements.append({"id": "person_identifiable_behaviour_join", "span": "behaviour sources"})
        if any(w in low for w in ("index", "score", "rank", "rangliste", "zuverl")):
            elements.append({"id": "aggregated_score_or_ranking", "span": "score/ranking"})
        if any(w in low for w in ("bonus", "fire", "dismiss", "bottom", "kündig", "entlass")):
            elements.append({"id": "adverse_action", "span": "adverse action"})
        conf = min(1.0, 0.3 + 0.23 * len(elements))
        return {"concept_id": "AIA-5-1-c", "elements": elements, "confidence": round(conf, 4)}


class AzureOpenAIJudge:
    """Live Azure OpenAI chat-completions backend (pinned deployment)."""

    def __init__(
        self,
        *,
        env: AzureOpenAIEnv | None = None,
        transport: Transport | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._env = env or read_azure_openai_env()
        self._transport = transport or UrllibTransport()
        self._timeout = timeout
        self.version = f"judge-azure-openai:{self._env.deployment}"

    @property
    def available(self) -> bool:
        return self._env.available

    def _url(self) -> str:
        return (
            f"{self._env.endpoint.rstrip('/')}/openai/deployments/{self._env.deployment}"
            f"/chat/completions?api-version={self._env.api_version}"
        )

    def complete_json(self, system: str, user: str) -> dict:
        payload = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        resp = self._transport.post_json(
            self._url(),
            headers={"api-key": self._env.key},
            payload=payload,
            timeout=self._timeout,
        )
        body = check_response(resp)  # raises on 401/403/429/5xx
        content = body["choices"][0]["message"]["content"]
        return json.loads(content)


class JudgeAdapter:
    name = "judge"

    def __init__(self, backend: JudgeBackend | None = None, *, enabled: bool = False) -> None:
        self._backend = backend
        self._enabled = enabled

    def available(self) -> bool:
        if not self._enabled or self._backend is None:
            return False
        # A live Azure backend reports its own availability; the stub is always on.
        return getattr(self._backend, "available", True)

    def detect(self, event: Event) -> list[dict]:
        if not self.available():
            return []  # off by default / no creds -> fall back to stages 0-1
        raw = self._backend.complete_json(RUBRIC, event.text)
        return [_parse_judge_json(raw, self._backend.version)]


def _parse_judge_json(raw: dict, backend_version: str) -> dict:
    concept_id = raw.get("concept_id", "AIA-5-1-c")
    elements = raw.get("elements", []) or []
    element_ids = [e["id"] for e in elements if isinstance(e, dict) and e.get("id")]
    spans = [e.get("span", "") for e in elements if isinstance(e, dict)]
    confidence = float(raw.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))
    label = Label(
        concept_id=concept_id,
        confidence=round(confidence, 4),
        elements_met=element_ids,
        evidence_refs=[f"judge:span:{s}" for s in spans if s],
        detector_versions={"judge": ADAPTER_VERSION, "backend": backend_version},
    )
    return label.to_dict()
