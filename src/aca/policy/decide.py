"""Python mirror of the OPA tier policy (policy/tier.rego).

OPA is the authoritative decision point in production and CI (`opa test`). This
module reimplements the *same* logic in Python for two reasons:

1. The gateway/Guard integration and the demo need an in-process decision when
   an OPA sidecar is not wired in yet.
2. It lets the decision logic be unit-tested with pytest in environments where
   the `opa` binary is unavailable. ``tests/test_policy_mirror.py`` asserts the
   mirror matches the cases in ``policy/tier_test.rego`` one-for-one.

If the two ever diverge, that is a bug: `policy/tier.rego` is authoritative.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_POLICY_DATA = Path(__file__).resolve().parents[3] / "policy" / "data"

# Decision order, strictest first.
_ORDER = {"deny": 3, "four-eyes": 2, "ask": 1, "allow": 0}


@dataclass(frozen=True)
class PolicyData:
    thresholds: dict[str, dict[str, Any]]
    confirmed_prohibited_patterns: list[str]


def load_policy_data(data_dir: Path | None = None) -> PolicyData:
    base = data_dir or _POLICY_DATA
    thresholds = json.loads((base / "thresholds.json").read_text(encoding="utf-8"))["thresholds"]
    confirmed = json.loads(
        (base / "confirmed_prohibited_patterns.json").read_text(encoding="utf-8")
    )["confirmed_prohibited_patterns"]
    return PolicyData(thresholds=thresholds, confirmed_prohibited_patterns=confirmed)


def decide(labels: list[dict], data: PolicyData) -> str:
    """Map labels + signed data to a tier. Strictest matching outcome wins.

    deny  -> a label's pattern_id is a confirmed prohibited pattern
    four-eyes -> concept at/above `high` confidence AND >= `min_elements`
    ask   -> concept at/above `low` confidence
    allow -> otherwise
    """
    best = "allow"

    def consider(candidate: str) -> None:
        nonlocal best
        if _ORDER[candidate] > _ORDER[best]:
            best = candidate

    for label in labels:
        pattern_id = label.get("pattern_id")
        if pattern_id and pattern_id in data.confirmed_prohibited_patterns:
            consider("deny")
            continue

        concept_id = label.get("concept_id")
        elements_met = label.get("elements_met") or []
        elements_total = label.get("elements_total")

        # Four-eyes requires a FULL, VALIDATED element match: every legal element
        # present AND the label is not merely a similarity signal. A
        # similarity_only label, or any label short of a full match, can never
        # reach four-eyes — it is ASK at most. BLOCK/four-eyes only on a full
        # element match; everything uncertain to ASK.
        if (elements_total and len(set(elements_met)) >= elements_total
                and not label.get("similarity_only")):
            consider("four-eyes")

        # A PARTIAL pattern (some-but-not-all elements) routes to ask (human
        # review), never allow, regardless of confidence.
        if label.get("partial_pattern"):
            consider("ask")

        # Phase A: a similarity_only signal (confident margin, no full element
        # match) routes to ASK — never four-eyes/deny. It only ever adds review.
        if label.get("similarity_only"):
            consider("ask")

        th = data.thresholds.get(concept_id)
        if not th:
            continue
        confidence = float(label.get("confidence", 0.0))

        # Similarity fallback to ASK (never four-eyes) when elements were not
        # fully marked: at/above the low threshold routes to a human. The old
        # confidence-only four-eyes path is removed — four-eyes needs the full
        # element match above, not a high embedding score alone.
        if confidence >= th["low"]:
            consider("ask")

    return best
