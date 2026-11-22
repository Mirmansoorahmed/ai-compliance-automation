"""Optional closed-vendor DecisionBackend — TypeSafe Jev (``jev-1``). OFF by default.

This backend is a documented, opt-in integration. It is DISABLED unless the
operator sets both:

    VAGUELAW_JEV_ENABLED=1
    VAGUELAW_JEV_API_KEY=<the operator's own key>

Hard rules enforced here:
  - It is never constructed or called in tests or in the default demo.
  - Enabling it is the operator's decision, with the operator's own key.
  - Sending data to it is an Art. 44 GDPR international-transfer event and a
    vendor-risk decision; only SYNTHETIC data may be sent. The backend refuses
    to run unless the caller passes synthetic_ok=True, acknowledging this.
  - Only the vendor's public HTTP API is used; no vendor code is copied.

If the key or the enable flag is missing, construction raises, so an accidental
import can never silently reach the vendor.
"""

from __future__ import annotations

import json
import os
import urllib.request

from aca.vaguelaw.backend import Answer, Question

JEV_ENABLED_ENV = "VAGUELAW_JEV_ENABLED"
JEV_KEY_ENV = "VAGUELAW_JEV_API_KEY"
JEV_URL_ENV = "VAGUELAW_JEV_URL"
_DEFAULT_URL = "https://api.typesafe.example/jev-1/decide"  # placeholder; operator sets the real one


class JevBackendDisabled(RuntimeError):
    pass


class JevBackend:
    name = "jev"

    def __init__(self, *, synthetic_ok: bool = False, opener=urllib.request.urlopen):
        if os.environ.get(JEV_ENABLED_ENV) != "1":
            raise JevBackendDisabled(
                f"Jev backend is disabled. Set {JEV_ENABLED_ENV}=1 and {JEV_KEY_ENV} "
                "to enable it (operator's own key; synthetic data only)."
            )
        key = os.environ.get(JEV_KEY_ENV)
        if not key:
            raise JevBackendDisabled(f"{JEV_KEY_ENV} is not set; refusing to enable the Jev backend.")
        if not synthetic_ok:
            raise JevBackendDisabled(
                "Calling the Jev backend is an Art. 44 transfer and a vendor-risk decision; "
                "pass synthetic_ok=True to confirm only synthetic data is sent."
            )
        self._key = key
        self._url = os.environ.get(JEV_URL_ENV, _DEFAULT_URL)
        self._opener = opener

    def decide(self, state: str, questions: list[Question]) -> list[Answer]:
        payload = {
            "model": "jev-1",
            "state": state,
            "questions": [{"id": q.id, "question": q.question} for q in questions],
        }
        req = urllib.request.Request(
            self._url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._key}"},
            method="POST",
        )
        with self._opener(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        answers: list[Answer] = []
        for item in body.get("answers", []):
            answers.append(Answer(
                question_id=item["id"],
                answer=bool(item.get("answer")),
                p_yes=float(item.get("p_yes", 0.5)),
                backend="jev:jev-1",
                rationale="vendor jev-1 (closed; Art. 44 transfer; synthetic data only)",
            ))
        return answers
