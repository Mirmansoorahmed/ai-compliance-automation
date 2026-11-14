"""Stage 0 — deterministic signals (R3.3).

Regex/keyword detectors for PII and secrets, plus tool data-class tags and a
few known schema patterns. Stage 0 is cheap, deterministic, and always runs,
including as the fallback when stages 1-3 are unavailable.

Stage 0 does NOT decide anything. It contributes *signals* that stage 1 and the
label builder fold into labels. It is deliberately conservative: it only reports
what it can match with a regex, never a legal verdict.

No third-party dependency: an open-source PII detector (e.g. Presidio) may be
vendored later as an optional enhancement; this stdlib path is the guaranteed
one for the oss profile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from aca.guard.event import Event

STAGE0_VERSION = "stage0/0.1.0"

# Deliberately simple, synthetic-data-friendly detectors. These are signals,
# not ground truth.
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# German + generic national-id-ish / employee-id-ish patterns (synthetic).
_EMPLOYEE_ID_RE = re.compile(r"\b(?:emp|empl|mitarbeiter|personal)[-_ ]?(?:id|nr)\b", re.IGNORECASE)
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
_SECRET_RE = re.compile(
    r"\b(?:api[_-]?key|secret|token|password|passwort)\b\s*[:=]", re.IGNORECASE
)

# Behaviour-source hints (DE + EN), used by stage 0 and reused by stage A.
# These are general workplace behaviour-monitoring sources, not tokens copied
# from any one request. The list is intentionally broad so the deterministic
# stage recognises the common ways employee behaviour is captured.
_BEHAVIOUR_HINTS = {
    "en": [
        "badge", "swipe", "slack activity", "slack message", "canteen", "cafeteria",
        "attendance", "keystroke", "productivity", "turnstile", "entry-gate",
        "entry gate", "door-access", "door access", "parking-gate", "parking gate",
        "vpn login", "login time", "login punctuality", "helpdesk ticket",
        "meeting attendance", "teams presence", "printer usage", "cctv", "camera",
        "phone-call log", "phone call log", "wearable", "step count", "commit count",
        "email response", "chat sentiment", "chat tone", "messaging-tool",
        "messaging tool", "lunchroom",
    ],
    "de": [
        "ausweis", "zutritt", "zutritts", "kantine", "anwesenheit", "tastatur",
        "produktivität", "drehkreuz", "eingang", "türzutritt", "parkschranke",
        "vpn-anmeldung", "anmeldezeit", "login-pünktlichkeit", "helpdesk",
        "meeting-teilnahme", "teams-präsenz", "druckernutzung", "kamera",
        "telefonprotokoll", "wearable", "schrittzahl", "commit", "e-mail-reaktion",
        "chat-stimmung", "chatton", "nachrichtentool", "essensausgabe",
    ],
}
_SCORE_HINTS = {
    "en": [
        "reliability index", "dependability score", "loyalty index", "productivity grade",
        "trust rating", "commitment score", "engagement score", "ranking", "rank",
        "score", "rating", "league table", "leaderboard", "index per", "grade",
        "dependability", "0-100", "scale",
    ],
    "de": [
        "zuverlässigkeitsindex", "verlässlichkeitswert", "loyalitätsindex",
        "produktivitätsnote", "vertrauensbewertung", "engagement-score", "rangliste",
        "rangfolge", "bewertung", "punktzahl", "bestenliste", "note", "skala", "index",
    ],
}
_ADVERSE_HINTS = {
    "en": [
        "bonus", "fire", "dismiss", "dismissal", "terminate", "termination",
        "penalise", "penalize", "demote", "bottom 10%", "bottom quartile",
        "lowest 5%", "lowest-ranked", "lowest decile", "deny promotion",
        "withhold bonus", "cut overtime", "night shift", "incentive",
        "remove from", "reassign", "perk",
    ],
    "de": [
        "bonus", "kündigen", "kündigung", "entlassen", "abmahnung", "degradieren",
        "beförderung verweigern", "überstunden", "nachtschicht", "prämie",
        "streiche", "versetze", "zusatzleistung", "verweigere",
    ],
}


@dataclass(frozen=True)
class Stage0Signals:
    has_pii: bool = False
    has_secret: bool = False
    pii_kinds: list[str] = field(default_factory=list)
    data_class: str | None = None
    behaviour_hits: int = 0
    score_hits: int = 0
    adverse_hits: int = 0
    version: str = STAGE0_VERSION

    def to_evidence_refs(self) -> list[str]:
        refs = []
        for kind in self.pii_kinds:
            refs.append(f"stage0:pii:{kind}")
        if self.has_secret:
            refs.append("stage0:secret")
        if self.behaviour_hits:
            refs.append(f"stage0:behaviour_hits={self.behaviour_hits}")
        if self.score_hits:
            refs.append(f"stage0:score_hits={self.score_hits}")
        if self.adverse_hits:
            refs.append(f"stage0:adverse_hits={self.adverse_hits}")
        return refs


def _count_hints(text_low: str, table: dict[str, list[str]]) -> int:
    count = 0
    for hints in table.values():
        for h in hints:
            if h in text_low:
                count += 1
    return count


def run_stage0(event: Event) -> Stage0Signals:
    text = f"{event.text}\n{event.artefact}"
    low = text.lower()

    pii_kinds: list[str] = []
    if _EMAIL_RE.search(text):
        pii_kinds.append("email")
    if _EMPLOYEE_ID_RE.search(text):
        pii_kinds.append("employee_id")
    if _IBAN_RE.search(text):
        pii_kinds.append("iban")

    has_secret = bool(_SECRET_RE.search(text))
    data_class = event.tool.get("data_class")

    return Stage0Signals(
        has_pii=bool(pii_kinds),
        has_secret=has_secret,
        pii_kinds=pii_kinds,
        data_class=data_class,
        behaviour_hits=_count_hints(low, _BEHAVIOUR_HINTS),
        score_hits=_count_hints(low, _SCORE_HINTS),
        adverse_hits=_count_hints(low, _ADVERSE_HINTS),
    )
