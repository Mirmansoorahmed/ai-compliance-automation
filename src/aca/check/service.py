"""The /v1/check decision service (Phase 1).

Ties the Semantic Guard + the deterministic secret scan + use-case.yaml fields
to the catalog checks, then to a decision via the Python mirror of
policy/check.rego. Returns:

  {decision, check_ids, reasons, obligations, missing_artefacts}

Fail-safe: ANY error while producing a decision -> ASK (never a silent ALLOW,
never a crash to the caller).

The Guard is injectable so tests run with the hashed-fallback embedder and need
no model download.
"""

from __future__ import annotations

import logging

from aca.check.decide import CheckPolicy, decide_checks
from aca.check.detectors import detect
from aca.guard.event import Event

log = logging.getLogger("aca.check")

_FAILSAFE = {
    "decision": "ASK",
    "check_ids": [],
    "reasons": [{"check_id": None, "decision": "ASK", "source": "fail-safe",
                 "title": "error producing a decision; routed to a human", "obligations": []}],
    "obligations": [],
    "missing_artefacts": [],
}


class CheckService:
    def __init__(self, *, guard=None, policy: CheckPolicy | None = None, use_cases: dict | None = None):
        # ``guard`` must expose label_with_health(event) -> (labels, healthy) or
        # label(event) -> labels. ``use_cases`` maps a use_case id -> its dict.
        self._guard = guard
        self._policy = policy or CheckPolicy.load()
        self._use_cases = use_cases or {}

    def _labels(self, event: Event):
        if self._guard is None:
            return [], True
        if hasattr(self._guard, "label_with_health"):
            return self._guard.label_with_health(event)
        return self._guard.label(event), True

    def check(self, payload: dict) -> dict:
        try:
            return self._check(payload)
        except Exception as exc:  # fail-safe: any error -> ASK
            log.warning("check failed, failing safe to ASK: %s", exc)
            return dict(_FAILSAFE)

    def _check(self, payload: dict) -> dict:
        event_type = payload.get("event", "prompt")
        text = payload.get("text", "") or ""
        artefact = payload.get("artefact", "") or payload.get("diff", "") or ""
        tool = payload.get("tool", {})
        if isinstance(tool, str):
            tool = {"name": tool}

        # Resolve the use case: inline dict, or an id looked up in the registry.
        use_case = None
        uc_ref = payload.get("use_case")
        if isinstance(uc_ref, dict):
            use_case = uc_ref
        elif isinstance(uc_ref, str) and uc_ref in self._use_cases:
            use_case = self._use_cases[uc_ref]

        event = Event(text=text, tool=tool, artefact=artefact,
                      language=payload.get("language"))
        labels, healthy = self._labels(event)
        if not healthy:
            # Guard unavailable -> fail-safe ASK (deterministic path unaffected).
            return dict(_FAILSAFE)

        det = detect(event_type, text, artefact, labels, use_case)

        partial_social = bool(
            det.social_scoring_label
            and det.social_scoring_label.get("partial_pattern")
            and not det.social_scoring_label.get("pattern_id")
        )

        result = decide_checks(
            det.fired,
            self._policy,
            related=det.related,
            use_case=use_case,
            partial_social=partial_social,
        )
        out = result.to_dict()
        # Carry labels only (no raw text) for traceability, like /v1/labels.
        out["labels"] = labels
        return out
