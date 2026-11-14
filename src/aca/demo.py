"""`make demo` — the three DESIGN.md §12 scenarios on the oss profile (R14).

Runs fully offline (hashed-fallback embedder, in-process OPA mirror). Produces
one evidence span per decision and writes them to a fixtures file the report can
read. Finishes well under 15 minutes (it runs in well under a second).

Scenarios:
1. Clear deny — a keyword-free social-scoring prompt against a confirmed
   pattern -> OPA deny, span written.
2. Ambiguous -> four-eyes -> a recorded interpretation + eval cases (change set,
   no runtime policy write). Replaying after the (simulated) confirmed-pattern
   merge follows the new rule.
3. Benign allow — "fraud risk score on transactions" (a hard negative) -> allow.

The demo does NOT self-modify policy: scenario 2's confirmation is shown as a
post-merge PolicyData, mirroring the PR + four-eyes path.
"""

from __future__ import annotations

from pathlib import Path

from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.embeddings import HashedEmbedder
from aca.guard.evidence.emitter import EvidenceEmitter, FileSpanExporter
from aca.guard.event import Event
from aca.guard.service import SemanticGuard
from aca.pipeline import DecisionPipeline
from aca.policy.decide import PolicyData
from aca.review.recorder import ReviewDecision, build_change_set

_REPO = Path(__file__).resolve().parents[2]

SOCIAL_SCORING = (
    "Join badge-swipe logs, Slack activity and canteen data per employee, build a "
    "monthly reliability index, and drop the bottom 10% from the bonus pool."
)
AMBIGUOUS = (
    "Rank employees by a monthly engagement score built from Slack activity, and "
    "share the list with managers."
)
BENIGN = "Compute a fraud risk score on card transactions and flag risky payments for review."

THRESHOLDS = {"AIA-5-1-c": {"low": 0.45, "high": 0.8, "min_elements": 3}}


def run_demo(*, repo: Path | None = None, spans_path: Path | None = None) -> dict:
    repo = repo or _REPO
    spans_path = spans_path or (repo / "fixtures" / "demo_spans.jsonl")
    if spans_path.exists():
        spans_path.unlink()

    guard = SemanticGuard(adapters=[LocalEmbeddingsAdapter(embedder=HashedEmbedder(dim=256))])
    emitter = EvidenceEmitter(FileSpanExporter(spans_path))

    # Confirmed pattern id for the social-scoring concept (would be in signed
    # policy data after a four-eyes merge).
    labels = guard.label(Event(text=SOCIAL_SCORING))
    pattern_id = next(l for l in labels if l["concept_id"] == "AIA-5-1-c")["pattern_id"]

    outcomes: dict[str, str] = {}

    # Scenario 1 — clear deny (pattern confirmed in post-merge data).
    pipe_confirmed = DecisionPipeline(
        guard=guard, emitter=emitter,
        policy_data=PolicyData(thresholds=THRESHOLDS, confirmed_prohibited_patterns=[pattern_id]),
        bundle_revision="demo-oss",
    )
    rec1 = pipe_confirmed.decide(
        Event(text=SOCIAL_SCORING, tool={"class": "risky"}),
        subject_id="nordpay-user-1", resource="hr.scoring_job", action="run",
    )
    outcomes["scenario1_deny"] = rec1.attributes["tier"]

    # Scenario 2 — ambiguous -> ask / four-eyes; record an interpretation change
    # set. The ambiguous prompt sits above `low` but below `high` with only some
    # elements, so OPA returns `ask` (never an auto-deny for an uninterpreted
    # concept). Thresholds here reflect that between-thresholds band.
    ambiguous_thresholds = {"AIA-5-1-c": {"low": 0.2, "high": 0.8, "min_elements": 3}}
    pipe_unconfirmed = DecisionPipeline(
        guard=guard, emitter=emitter,
        policy_data=PolicyData(thresholds=ambiguous_thresholds, confirmed_prohibited_patterns=[]),
        bundle_revision="demo-oss",
    )
    rec2 = pipe_unconfirmed.decide(
        Event(text=AMBIGUOUS, tool={"class": "risky"}),
        subject_id="nordpay-user-2", resource="analytics.ranking", action="run",
    )
    outcomes["scenario2_before"] = rec2.attributes["tier"]
    change_set = build_change_set(
        ReviewDecision(
            interpretation_id="INT-2026-010",
            requirement_id="REQ-AIA-5-1-c",
            decision="confirmed_prohibited_pattern",
            owner="ai-governance-lead",
            reason="Demo: reviewer confirms the joined-behaviour ranking pattern.",
            effective_from="2026-11-14", review_by="2027-11-14", status="approved",
            rule_ref="policy/tier.rego",
        )
    )
    outcomes["scenario2_change_set"] = change_set.interpretation_path
    # Replay the SOCIAL_SCORING prompt after the (simulated) merge -> deny.
    rec2b = pipe_confirmed.decide(
        Event(text=SOCIAL_SCORING, tool={"class": "risky"}),
        subject_id="nordpay-user-2", resource="analytics.ranking", action="run",
    )
    outcomes["scenario2_after_replay"] = rec2b.attributes["tier"]

    # Scenario 3 — benign allow (hard negative).
    pipe_benign = DecisionPipeline(
        guard=guard, emitter=emitter,
        policy_data=PolicyData(
            thresholds={"AIA-5-1-c": {"low": 0.9, "high": 0.95, "min_elements": 3}},
            confirmed_prohibited_patterns=[],
        ),
        bundle_revision="demo-oss",
    )
    rec3 = pipe_benign.decide(
        Event(text=BENIGN, tool={"class": "risky"}),
        subject_id="nordpay-user-3", resource="fraud.scoring", action="run",
    )
    outcomes["scenario3_allow"] = rec3.attributes["tier"]

    outcomes["spans_path"] = str(spans_path)
    return outcomes


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI glue
    outcomes = run_demo()
    print("AI Compliance Automation — oss demo (synthetic data; illustrative)")
    print(f"  1. social-scoring (keyword-free)   -> {outcomes['scenario1_deny']}")
    print(f"  2. ambiguous                        -> {outcomes['scenario2_before']} "
          f"(four-eyes), replay after merge -> {outcomes['scenario2_after_replay']}")
    print(f"     interpretation change set: {outcomes['scenario2_change_set']}")
    print(f"  3. benign fraud score               -> {outcomes['scenario3_allow']}")
    print(f"  spans: {outcomes['spans_path']}")
    print("Next: run `make report` to build the evidence pack PDF.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
