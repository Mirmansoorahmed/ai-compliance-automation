"""Evidence pack v2 (Phase 7).

Collects the decision records left at every enforcement point — the IDE hook,
the CI gate, the deploy gate, and the runtime gateway link — into one ordered
trace for a single use case, adds an ISO 42001 / EU AI Act mapping table and the
approval + break-glass records, and renders an auditor view. The PDF body
carries no code, file paths or hashes (an auditor-facing narrative only).
"""

from __future__ import annotations

from aca.evidence_pack.collect import (
    DecisionPoint,
    EvidenceTrace,
    build_trace,
    mapping_table,
)

__all__ = ["DecisionPoint", "EvidenceTrace", "build_trace", "mapping_table"]
