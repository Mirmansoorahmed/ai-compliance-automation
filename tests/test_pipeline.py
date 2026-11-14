"""Phase 6 — decision pipeline integration (Guard -> OPA mirror -> evidence).

Confirms a decision produces exactly one evidence span with the right tier, that
a Guard failure records a fail-safe tier (never a silent allow), and that no raw
body or clear identity leaks into the span.
"""

import json

from aca.guard.embeddings import HashedEmbedder
from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.evidence.emitter import EvidenceEmitter, FileSpanExporter
from aca.guard.event import Event
from aca.guard.service import SemanticGuard
from aca.pipeline import DecisionPipeline
from aca.policy.decide import PolicyData

BENIGN = "Compute a fraud risk score on card transactions and flag risky payments."


def _pipeline(tmp_path, *, policy_data=None, guard=None):
    guard = guard or SemanticGuard(adapters=[LocalEmbeddingsAdapter(embedder=HashedEmbedder(dim=256))])
    emitter = EvidenceEmitter(FileSpanExporter(tmp_path / "spans.jsonl"))
    pipe = DecisionPipeline.build(guard, emitter)
    if policy_data is not None:
        pipe.policy_data = policy_data
    return pipe, emitter


def test_benign_decision_records_single_allow_span(tmp_path):
    pipe, emitter = _pipeline(
        tmp_path,
        policy_data=PolicyData(
            thresholds={"AIA-5-1-c": {"low": 0.9, "high": 0.95, "min_elements": 3}},
            confirmed_prohibited_patterns=[],
        ),
    )
    rec = pipe.decide(
        Event(text=BENIGN, tool={"class": "risky"}),
        subject_id="alice@nordpay.example",
        resource="analytics.job",
        action="run",
        args={"sql": "SELECT * FROM txns"},
    )
    spans = emitter._exporter.read_all()
    assert len(spans) == 1
    assert rec.attributes["tier"] == "allow"
    assert rec.attributes["allowed"] is True
    # Privacy: no raw arg value, no clear identity in the span.
    blob = json.dumps(spans[0])
    assert "SELECT * FROM txns" not in blob
    assert "alice@nordpay.example" not in blob


def test_guard_failure_records_failsafe_ask_not_silent_allow(tmp_path):
    class _Boom:
        name = "boom"

        def detect(self, event):
            raise TimeoutError("guard timeout")

    pipe, emitter = _pipeline(tmp_path, guard=SemanticGuard(adapters=[_Boom()]))
    rec = pipe.decide(
        Event(text="anything", tool={"class": "risky"}),
        subject_id="s1",
        resource="r",
        action="a",
    )
    assert rec.attributes["tier"] == "ask"
    assert rec.attributes["allowed"] is False
    assert rec.attributes["reason_code"] == "guard_unavailable_failsafe"


def test_confirmed_pattern_decision_is_deny(tmp_path):
    social = (
        "Join badge-swipe logs, Slack activity and canteen data per employee, build a "
        "monthly reliability index, and drop the bottom 10% from the bonus pool."
    )
    guard = SemanticGuard(adapters=[LocalEmbeddingsAdapter(embedder=HashedEmbedder(dim=256))])
    labels = guard.label(Event(text=social))
    pattern_id = next(l for l in labels if l["concept_id"] == "AIA-5-1-c")["pattern_id"]
    pipe, emitter = _pipeline(
        tmp_path,
        guard=guard,
        policy_data=PolicyData(
            thresholds={"AIA-5-1-c": {"low": 0.45, "high": 0.8, "min_elements": 3}},
            confirmed_prohibited_patterns=[pattern_id],
        ),
    )
    rec = pipe.decide(
        Event(text=social, tool={"class": "risky"}),
        subject_id="s1",
        resource="hr.scoring",
        action="run",
    )
    assert rec.attributes["tier"] == "deny"
    assert rec.attributes["latency_ms"] is not None
