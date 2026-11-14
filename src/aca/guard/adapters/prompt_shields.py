"""Azure AI Content Safety — Prompt Shields adapter (R4.1, R4.4, R4.5, R4.6).

Prompt Shields detect jailbreak / prompt-injection style attacks. They do
**not** judge legal-element fit (Microsoft's own docs). This adapter therefore
emits a label under a *separate* concept id (``PROMPT-INJECTION``), never the
legal concept ids, so a Prompt Shields signal can never be mistaken for an
Art. 5 verdict and is scored separately from the local path (R4.5, R4.6).

Behaviour:
- No credentials (env vars absent) -> ``available() is False`` and ``detect``
  returns ``[]``. The Guard skips it; the oss path is unaffected (R4.4).
- Live call failure (timeout / 401 / 403 / 429 / 5xx) -> raises, so the Guard
  marks it failed and the pipeline applies the fail-safe tier (never a silent
  allow). See ``aca.guard.adapters.http_transport``.
- A detected attack is a *signal* (a label with confidence), never a verdict.

Config comes from environment variables only (no secrets in the repo).
"""

from __future__ import annotations

from aca.guard.adapters.azure_env import PromptShieldsEnv, read_prompt_shields_env
from aca.guard.adapters.http_transport import (
    Transport,
    UrllibTransport,
    check_response,
)
from aca.guard.event import Event
from aca.guard.labels.schema import Label

ADAPTER_VERSION = "prompt_shields/0.1.0"
CONCEPT_ID = "PROMPT-INJECTION"  # deliberately NOT a legal concept id


class PromptShieldsAdapter:
    name = "prompt_shields"

    def __init__(
        self,
        *,
        env: PromptShieldsEnv | None = None,
        transport: Transport | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._env = env or read_prompt_shields_env()
        self._transport = transport or UrllibTransport()
        self._timeout = timeout

    def available(self) -> bool:
        return self._env.available

    def _url(self) -> str:
        return (
            f"{self._env.endpoint.rstrip('/')}/contentsafety/text:shieldPrompt"
            f"?api-version={self._env.api_version}"
        )

    def detect(self, event: Event) -> list[dict]:
        if not self.available():
            # Degrade cleanly: no credentials -> no signal, no error.
            return []

        payload = {"userPrompt": event.text, "documents": []}
        resp = self._transport.post_json(
            self._url(),
            headers={"Ocp-Apim-Subscription-Key": self._env.key},
            payload=payload,
            timeout=self._timeout,
        )
        body = check_response(resp)  # raises on 401/403/429/5xx

        attack = _attack_detected(body)
        if not attack:
            return []

        label = Label(
            concept_id=CONCEPT_ID,
            confidence=0.99,  # Prompt Shields returns a boolean; map to high signal
            elements_met=["jailbreak_or_injection_detected"],
            evidence_refs=["prompt_shields:attackDetected"],
            detector_versions={"prompt_shields": ADAPTER_VERSION, "api_version": self._env.api_version},
        )
        return [label.to_dict()]


def _attack_detected(body: dict) -> bool:
    """Parse the Prompt Shields response shape defensively.

    The documented shape is:
        {"userPromptAnalysis": {"attackDetected": bool},
         "documentsAnalysis": [{"attackDetected": bool}, ...]}
    We treat an attack in the user prompt or any document as detected.
    """
    user = body.get("userPromptAnalysis") or {}
    if user.get("attackDetected"):
        return True
    for doc in body.get("documentsAnalysis") or []:
        if doc.get("attackDetected"):
            return True
    return False
