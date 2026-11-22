"""Assemble one evidence trace for a use case across all enforcement points.

A ``DecisionPoint`` is one recorded decision (editor hook / CI / deploy /
runtime). ``build_trace`` runs the same offline engines the phases use to
produce a coherent story for one use case — the CV-screening feature — and the
deploy gate twice (denied, then allowed after approvals). The result is an
ordered, auditor-readable trace plus the approval and break-glass records.

Everything here is a narrative record: no code, no file paths, no hashes. The
ISO 42001 / EU AI Act mapping table ties each control to where it is enforced.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aca.check.decide import CheckPolicy, decide_checks
from aca.check.deploy import decide_deploy
from aca.check.detectors import ANNEX_III_AREA_TO_CHECK, ANNEX_III_RELATED

_USE_CASE_ID = "uc-hr-cv-screening"


@dataclass(frozen=True)
class DecisionPoint:
    point: str          # "editor" | "ci" | "deploy" | "runtime"
    stage: str          # human label, e.g. "Prompt in the IDE"
    decision: str       # BLOCK | ASK | WARN | ALLOW | DENY | ALLOW
    summary: str        # one-line, no code/paths/hashes
    rules: list[str] = field(default_factory=list)


@dataclass
class EvidenceTrace:
    use_case_id: str
    use_case_title: str
    points: list[DecisionPoint] = field(default_factory=list)
    obligations: list[str] = field(default_factory=list)
    approvals: list[dict] = field(default_factory=list)
    break_glass: dict | None = None


def _cv_obligations() -> list[str]:
    fired = ["AIA-A3-4a"]
    related = list(ANNEX_III_RELATED.get("AIA-A3-4a", []))
    return decide_checks(fired, CheckPolicy.load(), related=related).obligations


def build_trace() -> EvidenceTrace:
    policy = CheckPolicy.load()
    obligations = _cv_obligations()

    points: list[DecisionPoint] = []

    # 1. Editor: the CV-screening prompt (WARN with obligations).
    cv = decide_checks(["AIA-A3-4a"], policy,
                       related=list(ANNEX_III_RELATED.get("AIA-A3-4a", [])))
    points.append(DecisionPoint(
        point="editor", stage="Prompt in the IDE (CV screening feature)",
        decision=cv.decision, rules=cv.check_ids,
        summary="High-risk recruitment use recognised; the developer is warned and the "
                "required artefacts are listed before any code is merged.",
    ))

    # 2. Editor: a social-scoring prompt is refused (BLOCK).
    social = decide_checks(["AIA-5-1-c"], policy)
    points.append(DecisionPoint(
        point="editor", stage="Prompt in the IDE (a prohibited request)",
        decision=social.decision, rules=social.check_ids,
        summary="A request amounting to social scoring is refused at the prompt.",
    ))

    # 3. CI: a secret in a PR diff is blocked (BLOCK).
    points.append(DecisionPoint(
        point="ci", stage="Pull request check",
        decision="BLOCK", rules=["SEC-SECRETS"],
        summary="A hardcoded credential added in the pull request fails the compliance check.",
    ))

    # 4. CI: the CV feature PR passes with a pending obligations checklist (WARN).
    points.append(DecisionPoint(
        point="ci", stage="Pull request check (CV feature)",
        decision="WARN", rules=cv.check_ids,
        summary="The feature is allowed to merge but the pull request shows a pending "
                "checklist of the artefacts still required before deployment.",
    ))

    # 5. Deploy: first attempt denied (artefacts missing).
    first = decide_deploy({"obligations": obligations,
                           "artefacts": {k: None for k in obligations}, "approvals": []})
    points.append(DecisionPoint(
        point="deploy", stage="First deploy attempt",
        decision=first.decision, rules=[],
        summary="Deployment to production is blocked because the required artefacts are "
                "missing and not yet approved.",
    ))

    # 6. Deploy: allowed after artefacts recorded + two distinct approvals.
    approvals = [
        {"artefact": "*", "approver": "compliance-officer"},
        {"artefact": "*", "approver": "engineering-lead"},
    ]
    approved = decide_deploy({"obligations": obligations,
                              "artefacts": {k: f"declared:{k}" for k in obligations},
                              "approvals": approvals})
    points.append(DecisionPoint(
        point="deploy", stage="Deploy after artefacts + two approvals",
        decision=approved.decision, rules=[],
        summary="Once every required artefact is recorded and approved by two different "
                "people, the deployment is allowed.",
    ))

    # 7. Runtime: the gateway denies a social-scoring tool call.
    points.append(DecisionPoint(
        point="runtime", stage="Runtime tool call at the Agent Trust Gateway",
        decision="DENY", rules=["AIA-5-1-c"],
        summary="At runtime the gateway denies a tool call that amounts to social scoring, "
                "consistent with the editor and CI decisions.",
    ))

    return EvidenceTrace(
        use_case_id=_USE_CASE_ID,
        use_case_title="CV pre-screening for apprenticeships",
        points=points,
        obligations=obligations,
        approvals=[{"artefact": "all required", "approver_role": "compliance officer"},
                   {"artefact": "all required", "approver_role": "engineering lead"}],
        break_glass={
            "used": False,
            "note": "No break-glass override was used for this use case.",
        },
    )


# ISO/IEC 42001 and EU AI Act controls mapped to where each is enforced.
_MAPPING = [
    {"control": "ISO 42001 A.6.2 — AI system impact assessment",
     "act": "EU AI Act Art. 27 (FRIA) / Art. 9 (risk management)",
     "enforced_at": "Deploy gate (artefact required + approved)"},
    {"control": "ISO 42001 A.5.2 — intended use documented",
     "act": "EU AI Act Art. 26(7) (worker information)",
     "enforced_at": "Editor warning + CI checklist + deploy gate"},
    {"control": "ISO 42001 A.8.3 — information for interested parties",
     "act": "EU AI Act Art. 50 (transparency)",
     "enforced_at": "Vague-law classifier (Art. 50 question)"},
    {"control": "ISO 42001 A.9.2 — human oversight",
     "act": "EU AI Act Art. 14 (oversight plan)",
     "enforced_at": "Deploy gate (oversight plan artefact)"},
    {"control": "ISO 42001 A.3.3 — concern reporting channel",
     "act": "—",
     "enforced_at": "Decision messages name the concern channel"},
    {"control": "GDPR Art. 35 (DPIA) / Art. 22 (automated decisions)",
     "act": "EU AI Act Annex III high-risk duties",
     "enforced_at": "Editor + CI + deploy gate + runtime"},
]


def mapping_table() -> list[dict]:
    return list(_MAPPING)
