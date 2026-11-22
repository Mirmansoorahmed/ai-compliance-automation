"""Deploy-gate decision (Python mirror of policy/deploy.rego).

The CI gate (Phase 3) warns and lists obligations; the deploy gate (Phase 4) is
where those obligations must actually be satisfied before a high-risk feature
reaches production. It is deliberately strict and deterministic:

A deploy is ALLOWED only when, for the feature's required obligations:
  1. every required artefact has a non-empty path recorded in use-case.yaml, and
  2. every required artefact is approved by TWO DISTINCT people (four-eyes), and
  3. no break-glass override is in force without a recorded justification.

Otherwise the deploy is DENIED and the reasons name exactly what is missing
(e.g. "DPIA artefact missing", "oversight_plan has only one approver").

Input model (what the gate receives, assembled from use-case.yaml + the
decision engine's obligations list):

    {
      "use_case_id": "uc-hr-cv-screening",
      "obligations": ["risk_management", "dpia", "oversight_plan", ...],
      "artefacts": {"dpia": "docs/dpia.md", "oversight_plan": null, ...},
      "approvals": [
        {"artefact": "dpia", "approver": "alice"},
        {"artefact": "dpia", "approver": "bob"},
        ...
      ],
      "break_glass": {"active": false, "justification": "", "approver": ""}
    }

``approvals`` may also be a flat list of approver names applied to the whole
feature; then each required artefact needs two distinct approvers overall.

OPA (policy/deploy.rego) is authoritative; this mirror lets the service, tests
and the offline demo run without an opa binary. If they diverge, that is a bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field

REQUIRED_APPROVERS = 2


@dataclass
class DeployResult:
    decision: str  # "ALLOW" | "DENY"
    reasons: list[str] = field(default_factory=list)
    missing_artefacts: list[str] = field(default_factory=list)
    under_approved: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reasons": self.reasons,
            "missing_artefacts": self.missing_artefacts,
            "under_approved": self.under_approved,
        }


def _present(artefacts: dict, key: str) -> bool:
    val = artefacts.get(key)
    return isinstance(val, str) and bool(val.strip())


def _approvers_for(approvals, key: str) -> set[str]:
    """Distinct approver identities covering artefact ``key``.

    Supports two approval shapes:
      - records: {"artefact": <key|"*"|"all">, "approver": <who>}
      - flat names: ["alice", "bob"] (apply to every artefact)
    """
    approvers: set[str] = set()
    for item in approvals or []:
        if isinstance(item, str):
            approvers.add(item)
            continue
        if isinstance(item, dict):
            who = item.get("approver") or item.get("by") or item.get("name")
            if not who:
                continue
            art = item.get("artefact") or item.get("obligation") or "*"
            if art in (key, "*", "all"):
                approvers.add(str(who))
    return approvers


def decide_deploy(payload: dict) -> DeployResult:
    obligations = list(payload.get("obligations") or [])
    artefacts = payload.get("artefacts") or {}
    approvals = payload.get("approvals") or []
    break_glass = payload.get("break_glass") or {}

    # Break-glass: an active override with a recorded justification + approver
    # allows the deploy but is itself a reason (audited). Without a justification
    # it does not count.
    if break_glass.get("active") and str(break_glass.get("justification", "")).strip() \
            and str(break_glass.get("approver", "")).strip():
        return DeployResult(
            decision="ALLOW",
            reasons=[f"break-glass override by {break_glass['approver']}: {break_glass['justification']}"],
        )

    missing: list[str] = []
    under: list[str] = []
    reasons: list[str] = []

    for key in obligations:
        if not _present(artefacts, key):
            missing.append(key)
            reasons.append(f"{key} artefact missing")
            continue
        approvers = _approvers_for(approvals, key)
        if len(approvers) < REQUIRED_APPROVERS:
            under.append(key)
            reasons.append(
                f"{key} has {len(approvers)} approver(s); {REQUIRED_APPROVERS} distinct required")

    if missing or under:
        return DeployResult(decision="DENY", reasons=reasons,
                            missing_artefacts=missing, under_approved=under)

    return DeployResult(decision="ALLOW",
                        reasons=["all required artefacts present and approved by two distinct people"])
