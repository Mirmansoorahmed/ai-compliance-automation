"""Map a /v1/check event to the catalog check-ids that fired.

Three sources of a fired check, kept deliberately narrow and testable for the
Phase-1 mappings (ARCHITECTURE stories A, B, C):

1. Semantic Guard labels. The local Guard labels the Art. 5(1)(c) social-scoring
   concept (concept_id ``AIA-5-1-c``). A full-pattern label fires AIA-5-1-c; a
   partial pattern is reported so OPA can route it to ASK rather than ALLOW.
2. Deterministic secret scan on tool/diff events -> SEC-SECRETS.
3. use-case.yaml fields:
   - each ``annex_iii`` area maps to its Annex III check (e.g. "4(a)" ->
     AIA-A3-4a, "5(b)" -> AIA-A3-5b), plus the related obligations/checks the
     catalog lists for that area.

This module does NOT decide anything; it returns fired check-ids (and the
social-scoring label so the caller can tell a full pattern from a partial one).
OPA / the Python mirror makes the decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aca.check.secrets import scan_secrets

# Annex III area string (as written in use-case.yaml) -> catalog check id.
ANNEX_III_AREA_TO_CHECK = {
    "1(a)": "AIA-A3-1a", "1(b)": "AIA-A3-1b", "1(c)": "AIA-A3-1c",
    "2": "AIA-A3-2",
    "3(a)": "AIA-A3-3a", "3(b)": "AIA-A3-3b", "3(c)": "AIA-A3-3c", "3(d)": "AIA-A3-3d",
    "4(a)": "AIA-A3-4a", "4(b)": "AIA-A3-4b",
    "5(a)": "AIA-A3-5a", "5(b)": "AIA-A3-5b", "5(c)": "AIA-A3-5c", "5(d)": "AIA-A3-5d",
    "6": "AIA-A3-6a-e", "7": "AIA-A3-7a-d", "8(a)": "AIA-A3-8a", "8(b)": "AIA-A3-8b",
}

# Related checks that a given Annex III area pulls in (the companion legal
# duties named in the catalog for that area). Kept explicit and small for v1.
ANNEX_III_RELATED = {
    "AIA-A3-4a": ["GDPR-22", "GDPR-35", "AIA-26-7", "DE-BETRVG-87"],
    "AIA-A3-4b": ["GDPR-35", "AIA-26-7", "DE-BETRVG-87"],
    "AIA-A3-5b": ["AIA-27", "GDPR-22", "GDPR-35"],
    "AIA-A3-5c": ["AIA-27", "GDPR-35"],
}


@dataclass
class Detection:
    # Primary checks: their catalog decision drives the tier.
    fired: list[str] = field(default_factory=list)
    # Related/companion checks: they add article references + obligations but are
    # clamped to WARN in the bundle (they are legal duties attached to a
    # high-risk use case, not independent gates), UNLESS escalated explicitly.
    related: list[str] = field(default_factory=list)
    secret_kinds: list[str] = field(default_factory=list)
    social_scoring_label: dict | None = None  # the AIA-5-1-c label, if any

    def add(self, check_id: str) -> None:
        if check_id and check_id not in self.fired:
            self.fired.append(check_id)

    def add_related(self, check_id: str) -> None:
        if check_id and check_id not in self.related and check_id not in self.fired:
            self.related.append(check_id)


def _social_label(labels: list[dict]) -> dict | None:
    for label in labels or []:
        if label.get("concept_id") == "AIA-5-1-c":
            return label
    return None


def detect(event_type: str, text: str, artefact: str, labels: list[dict], use_case: dict | None) -> Detection:
    """Return the fired catalog check-ids for one event."""
    det = Detection()

    # (1) Semantic Guard: social scoring. A full pattern fires AIA-5-1-c (BLOCK);
    # a partial pattern is carried so the decision layer routes it to ASK.
    label = _social_label(labels)
    if label is not None:
        det.social_scoring_label = label
        if label.get("pattern_id"):          # full three-element match
            det.add("AIA-5-1-c")
        elif label.get("partial_pattern"):   # 2 of 3 elements -> ASK, not ALLOW
            det.add("AIA-5-1-c")

    # (2) Deterministic secret scan on tool/diff events.
    if event_type in ("tool", "diff"):
        kinds = scan_secrets(f"{text}\n{artefact}")
        if kinds:
            det.secret_kinds = kinds
            det.add("SEC-SECRETS")

    # (3) use-case.yaml declared Annex III areas + their companion duties.
    if use_case:
        solely_automated = use_case.get("decision_effect") == "solely_automated"
        for area in use_case.get("annex_iii", []) or []:
            check_id = ANNEX_III_AREA_TO_CHECK.get(str(area))
            if not check_id:
                continue
            det.add(check_id)  # primary high-risk check (WARN) drives the tier
            for related in ANNEX_III_RELATED.get(check_id, []):
                # GDPR Art. 22 (solely-automated decisions) escalates the bundle
                # to ASK only when the declared decision effect is solely
                # automated (SCHUFA). Otherwise it is a WARN-clamped reference.
                if related == "GDPR-22" and solely_automated:
                    det.add(related)
                else:
                    det.add_related(related)

    return det
