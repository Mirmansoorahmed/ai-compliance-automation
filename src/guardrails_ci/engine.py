"""Run the /v1/check decision engine in-process over a parsed diff.

No HTTP service is needed: the gate builds the same ``CheckService`` the API
builds (Semantic Guard with the offline hashed-fallback embedder + the catalog
policy) and calls ``check`` on an event derived from the diff. Added lines are
sent as a ``diff`` event so the deterministic secret scan and the artefact stage
see them; the repo's use-case.yaml is passed inline so Annex III areas pull in
their obligations.

A local secret pre-check (reusing guardrails_hook.secrets) runs first and forces
BLOCK, mirroring the hook: a secret in added lines fails the gate regardless of
anything else.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from guardrails_ci.diff import Diff
from guardrails_hook.secrets import has_secret

# Reuse the exact offline wiring the Phase-1 demo uses.
from aca.check.service import CheckService
from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.embeddings import build_embedder
from aca.guard.service import SemanticGuard


@dataclass
class CiResult:
    decision: str
    check_ids: list[str] = field(default_factory=list)
    reasons: list[dict] = field(default_factory=list)
    obligations: list[str] = field(default_factory=list)
    missing_artefacts: list[str] = field(default_factory=list)
    local_secret: bool = False
    raw: dict = field(default_factory=dict)


def build_check_service() -> CheckService:
    """The same service /v1/check uses, wired for offline reproducibility."""
    embedder = build_embedder(allow_hashed_fallback=True, dim=256)
    guard = SemanticGuard(adapters=[LocalEmbeddingsAdapter(embedder=embedder, dim=256)])
    return CheckService(guard=guard)


def evaluate(diff: Diff, use_case: dict | None, *, service: CheckService | None = None) -> CiResult:
    svc = service or build_check_service()
    added = diff.added_text

    # The event: added lines as a diff-type artefact (secret scan + Stage A),
    # with the use case inline so Annex III obligations resolve.
    payload = {
        "event": "diff",
        "tool": "ci",
        "text": "",
        "artefact": added,
    }
    if use_case is not None:
        payload["use_case"] = use_case

    out = svc.check(payload)

    return CiResult(
        decision=out.get("decision", "ASK"),
        check_ids=out.get("check_ids", []),
        reasons=out.get("reasons", []),
        obligations=out.get("obligations", []),
        missing_artefacts=out.get("missing_artefacts", []),
        local_secret=has_secret(added),
        raw=out,
    )
