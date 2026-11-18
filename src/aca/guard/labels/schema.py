"""Semantic Guard label schema (R3.1, R3.8).

The Guard emits *labels*, never a verdict. A label records which legal-concept
elements appear present, with what confidence, what evidence supports it, and
which detector versions produced it (for reproducibility / audit).

Label shape (DESIGN.md §5.4):
    {
      "concept_id": str,
      "pattern_id": str | None,
      "elements_met": [str, ...],
      "confidence": float in [0, 1],
      "evidence_refs": [str, ...],
      "detector_versions": {stage_name: version, ...}
    }

A label MUST NOT carry an authorization verdict. ``VERDICT_FIELDS`` lists the
fields that would make it a verdict; ``is_verdict_free`` enforces their absence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

# Fields that would turn a label into a verdict. The Guard must never set these;
# only OPA decides allow/ask/four-eyes/deny.
VERDICT_FIELDS = frozenset({"tier", "decision", "allow", "allowed", "deny", "verdict"})


@dataclass(frozen=True)
class Label:
    concept_id: str
    confidence: float
    elements_met: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    detector_versions: dict[str, str] = field(default_factory=dict)
    pattern_id: str | None = None
    # Count of the concept's total legal elements, so OPA can tell a full match
    # (all elements) from a partial one (some, but not all). This is a *signal*,
    # not a verdict — OPA still decides allow/ask/four-eyes/deny.
    elements_total: int | None = None
    # True when some-but-not-all elements are present (a "partial pattern").
    partial_pattern: bool = False

    def __post_init__(self) -> None:
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence!r}")
        if not self.concept_id:
            raise ValueError("concept_id is required")

    def to_dict(self) -> dict:
        d = asdict(self)
        # Omit a null pattern_id for cleaner payloads.
        if d.get("pattern_id") is None:
            d.pop("pattern_id")
        if d.get("elements_total") is None:
            d.pop("elements_total")
        if not d.get("partial_pattern"):
            d.pop("partial_pattern")
        return d


def is_verdict_free(label: dict) -> bool:
    """True if the label dict carries no verdict field (R3.2)."""
    return VERDICT_FIELDS.isdisjoint(label.keys())


def validate_label(label: dict) -> list[str]:
    """Return a list of problems with a label dict (empty = valid)."""
    errors: list[str] = []
    if not label.get("concept_id"):
        errors.append("missing concept_id")
    conf = label.get("confidence")
    if not isinstance(conf, (int, float)) or isinstance(conf, bool):
        errors.append("confidence must be a number")
    elif not (0.0 <= float(conf) <= 1.0):
        errors.append("confidence must be in [0, 1]")
    if not isinstance(label.get("elements_met", []), list):
        errors.append("elements_met must be a list")
    if not is_verdict_free(label):
        bad = sorted(VERDICT_FIELDS.intersection(label.keys()))
        errors.append(f"label carries verdict field(s): {bad} (Guard emits labels only)")
    return errors
