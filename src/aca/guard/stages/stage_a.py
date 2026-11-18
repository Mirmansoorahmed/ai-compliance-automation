"""Stage A — artefact / diff analysis (R3.6).

Static checks on code or a diff for the three Art. 5(1)(c) social-scoring
elements:

1. a person-ID join across behaviour sources,
2. an aggregated score / ranking,
3. an adverse action driven by that score.

These are heuristic static signals on synthetic code, not a verdict. The result
is folded into a label by the caller; OPA still decides.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

STAGE_A_VERSION = "stageA/0.1.0"

# Join on a person identifier across sources.
_JOIN_RE = re.compile(
    r"\b(?:join|merge|concat|groupby|group_by)\b.*\b(?:employee|person|staff|user|mitarbeiter)[_ ]?id\b",
    re.IGNORECASE | re.DOTALL,
)
# Behaviour sources that, joined per person, indicate social-scoring inputs.
# Identifiers use underscores (badge_logs, slack_activity), so match the keyword
# as a substring rather than requiring a trailing word boundary.
_BEHAVIOUR_SRC_RE = re.compile(
    r"(badge|swipe|slack|canteen|attendance|keystroke|zutritt|kantine|anwesenheit)",
    re.IGNORECASE,
)
# An aggregated score / ranking produced from the join.
_SCORE_RE = re.compile(
    r"(reliability[_ ]?index|score|ranking|rank|rating|zuverl\w*index|rangliste)",
    re.IGNORECASE,
)
# An adverse action taken on the score.
_ADVERSE_RE = re.compile(
    r"(bonus|fire|dismiss|terminate|demote|penal(?:ise|ize)|bottom\s*\d+%|k\w*ndig\w*|entlass\w*)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StageAResult:
    has_person_join: bool
    has_aggregated_score: bool
    has_adverse_action: bool
    behaviour_source_count: int
    version: str = STAGE_A_VERSION

    @property
    def elements_met(self) -> list[str]:
        met = []
        if self.has_person_join and self.behaviour_source_count >= 2:
            met.append("person_identifiable_behaviour_join")
        if self.has_aggregated_score:
            met.append("aggregated_score_or_ranking")
        if self.has_adverse_action:
            met.append("adverse_action")
        return met

    @property
    def all_elements(self) -> bool:
        return len(self.elements_met) == 3


def run_stage_a(artefact: str) -> StageAResult:
    sources = set(m.group(1).lower() for m in _BEHAVIOUR_SRC_RE.finditer(artefact))
    return StageAResult(
        has_person_join=bool(_JOIN_RE.search(artefact)),
        has_aggregated_score=bool(_SCORE_RE.search(artefact)),
        has_adverse_action=bool(_ADVERSE_RE.search(artefact)),
        behaviour_source_count=len(sources),
    )
