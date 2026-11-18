"""Decide a /v1/check outcome from fired catalog checks (Python mirror of
policy/check.rego).

Precedence (strictest wins): BLOCK > ASK > WARN > ALLOW.
- Each fired check contributes its catalog decision, EXCEPT a social-scoring
  (AIA-5-1-c) label that is only a *partial* pattern: a partial pattern routes
  to ASK (a human), never BLOCK and never ALLOW — the full three-element
  pattern is required for an automatic BLOCK.
- ``obligations`` is the union of the required artefacts of every WARN/BLOCK
  check that has obligations (from policy/data/obligations.json).
- ``missing_artefacts`` are obligations whose path is absent (null/empty) in the
  use-case.yaml ``artefacts`` block.
- ``reasons`` carry the check id, its decision, the article/source, and the
  obligations for that check.

OPA (policy/check.rego) is authoritative; this mirror lets the service and tests
run in-process without an opa binary. If they diverge, that is a bug.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from aca.catalog.loader import load_catalog

_DATA_DIR = Path(__file__).resolve().parents[3] / "policy" / "data"

_ORDER = {"BLOCK": 3, "ASK": 2, "WARN": 1, "ALLOW": 0}
_RANK_TO_DECISION = {v: k for k, v in _ORDER.items()}


@dataclass(frozen=True)
class CheckPolicy:
    """Catalog-derived policy data: per-check decision, source, obligations."""
    decisions: dict
    sources: dict
    titles: dict
    obligations: dict

    @classmethod
    def load(cls, *, data_dir: Path | None = None, catalog_path: Path | None = None) -> "CheckPolicy":
        base = data_dir or _DATA_DIR
        obligations = json.loads((base / "obligations.json").read_text(encoding="utf-8"))["obligations"]
        catalog = load_catalog(catalog_path)["checks"]
        decisions = {c["id"]: c["dec"] for c in catalog}
        sources = {c["id"]: c.get("src", "") for c in catalog}
        titles = {c["id"]: c.get("title", "") for c in catalog}
        return cls(decisions=decisions, sources=sources, titles=titles, obligations=obligations)


@dataclass
class CheckResult:
    decision: str
    check_ids: list[str] = field(default_factory=list)
    reasons: list[dict] = field(default_factory=list)
    obligations: list[str] = field(default_factory=list)
    missing_artefacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "check_ids": self.check_ids,
            "reasons": self.reasons,
            "obligations": self.obligations,
            "missing_artefacts": self.missing_artefacts,
        }


_OBLIGATION_ORDER = [
    "risk_management", "dpia", "fria", "oversight_plan", "eval_report", "worker_information",
]


def _effective_decision(check_id: str, policy: CheckPolicy, partial_social: bool) -> str:
    dec = policy.decisions.get(check_id, "ALLOW")
    # A partial social-scoring pattern must not auto-BLOCK; route to ASK.
    if check_id == "AIA-5-1-c" and partial_social:
        return "ASK"
    return dec


def decide_checks(
    fired: list[str],
    policy: CheckPolicy,
    *,
    related: list[str] | None = None,
    use_case: dict | None = None,
    partial_social: bool = False,
) -> CheckResult:
    related = related or []
    if not fired and not related:
        return CheckResult(decision="ALLOW")

    best_rank = 0
    reasons: list[dict] = []
    obligations: set[str] = set()

    # Primary checks drive the tier with their catalog decision.
    for cid in fired:
        dec = _effective_decision(cid, policy, partial_social)
        best_rank = max(best_rank, _ORDER.get(dec, 0))
        _add_reason(reasons, obligations, policy, cid, dec)

    # Related/companion checks add article refs + obligations but are clamped to
    # WARN: they are legal duties attached to a high-risk use case, not gates.
    for cid in related:
        catalog_dec = policy.decisions.get(cid, "ALLOW")
        dec = "WARN" if _ORDER.get(catalog_dec, 0) > _ORDER["WARN"] else catalog_dec
        best_rank = max(best_rank, _ORDER.get(dec, 0))
        _add_reason(reasons, obligations, policy, cid, dec, clamped=(dec != catalog_dec))

    decision = _RANK_TO_DECISION[best_rank]
    obligations_list = [k for k in _OBLIGATION_ORDER if k in obligations]
    missing = _missing_artefacts(obligations_list, use_case)

    return CheckResult(
        decision=decision,
        check_ids=list(fired) + list(related),
        reasons=reasons,
        obligations=obligations_list,
        missing_artefacts=missing,
    )


def _add_reason(reasons, obligations, policy, cid, dec, *, clamped=False):
    obl = policy.obligations.get(cid, [])
    reason = {
        "check_id": cid,
        "decision": dec,
        "source": policy.sources.get(cid, ""),
        "title": policy.titles.get(cid, ""),
        "obligations": obl,
    }
    if clamped:
        reason["note"] = "companion duty for a high-risk use case; clamped to WARN in this bundle"
    reasons.append(reason)
    obligations.update(obl)


def _missing_artefacts(obligations: list[str], use_case: dict | None) -> list[str]:
    artefacts = (use_case or {}).get("artefacts") or {}
    missing = []
    for key in obligations:
        val = artefacts.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            missing.append(key)
    return missing
