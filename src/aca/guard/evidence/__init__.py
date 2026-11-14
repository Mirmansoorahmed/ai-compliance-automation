"""aca.guard.evidence package.

One OpenTelemetry-shaped span per decision, aligned with decision-record v1.
Privacy by default: pseudonymised subject, no clear identity, args reduced to
names/count/SHA-256, no raw prompt bodies. File exporter in the oss profile;
this repo is not the long-term store.
"""

from aca.guard.evidence.emitter import (
    EvidenceEmitter,
    FileSpanExporter,
    build_emitter,
)
from aca.guard.evidence.record import DecisionRecord, build_decision_record

__all__ = [
    "EvidenceEmitter",
    "FileSpanExporter",
    "build_emitter",
    "DecisionRecord",
    "build_decision_record",
]
