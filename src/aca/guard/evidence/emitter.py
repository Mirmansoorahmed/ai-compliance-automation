"""Evidence span emitter (R10.1, R10.4).

The oss profile uses a file exporter: one JSON line per span (JSONL), appended
to a spans file. This repo is NOT the long-term store — AI Audit Logging &
Monitoring (a sibling) consumes these later. The file export is a demo/CI sink
and a hand-off point.

If the OpenTelemetry SDK is installed, ``OTelExporter`` maps the same
decision-record attributes onto a real OTel span. The attribute set is
identical, so switching exporters does not change the evidence contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from aca.guard.evidence.record import DecisionRecord, build_decision_record


class SpanExporter(Protocol):
    def export(self, record: DecisionRecord) -> None:
        ...


class FileSpanExporter:
    """Appends one JSON object per decision to a JSONL spans file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, record: DecisionRecord) -> None:
        line = json.dumps(
            {"span_name": record.span_name, "attributes": record.attributes},
            sort_keys=True,
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]


class OTelExporter:  # pragma: no cover - requires the OTel SDK
    """Maps a decision record onto a real OpenTelemetry span when available."""

    def __init__(self, tracer_name: str = "aca.semantic_guard") -> None:
        from opentelemetry import trace  # type: ignore

        self._tracer = trace.get_tracer(tracer_name)

    def export(self, record: DecisionRecord) -> None:
        with self._tracer.start_as_current_span(record.span_name) as span:
            for key, value in record.attributes.items():
                # OTel attributes must be primitives/str; complex values are
                # JSON-encoded to preserve them losslessly.
                if isinstance(value, (str, bool, int, float)) or value is None:
                    span.set_attribute(key, value if value is not None else "")
                else:
                    span.set_attribute(key, json.dumps(value, sort_keys=True))


class EvidenceEmitter:
    """Builds a decision record and hands it to the configured exporter."""

    def __init__(self, exporter: SpanExporter) -> None:
        self._exporter = exporter

    def emit(self, **record_kwargs) -> DecisionRecord:
        record = build_decision_record(**record_kwargs)
        self._exporter.export(record)
        return record


def build_emitter(exporter: str = "file", *, path: str | Path = "evidence/spans.jsonl") -> EvidenceEmitter:
    """Return an emitter for the configured exporter (oss default: file)."""
    if exporter == "file":
        return EvidenceEmitter(FileSpanExporter(path))
    if exporter == "otel":  # pragma: no cover - requires the OTel SDK
        return EvidenceEmitter(OTelExporter())
    raise ValueError(f"unknown evidence exporter: {exporter!r}")
