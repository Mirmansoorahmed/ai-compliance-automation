"""Demo: the deploy gate denies, then allows (Phase 4), fully offline.

Story (Halvaro Payments GmbH, fictional): the CV-screening feature (Annex III
4(a) -> WARN) is ready to deploy. The deploy gate:

  1. First deploy  -> DENIED: the DPIA and oversight plan (and the rest) are
     missing, so production is blocked.
  2. After the artefacts are recorded in use-case.yaml AND each is approved by
     two distinct people -> ALLOWED.

The required obligations come from the same catalog the CI gate uses (no
hardcoded list); the gate decision is the Python mirror of policy/deploy.rego.
"""

from __future__ import annotations

from aca.check.decide import CheckPolicy, decide_checks
from aca.check.deploy import decide_deploy

# The CV-screening use case declares Annex III 4(a); its obligations come from
# the catalog via the same decision engine the CI gate uses.
_USE_CASE_ID = "uc-hr-cv-screening"
_FIRED = ["AIA-A3-4a"]
_RELATED = ["GDPR-22", "GDPR-35", "AIA-26-7", "DE-BETRVG-87"]


def _obligations() -> list[str]:
    result = decide_checks(_FIRED, CheckPolicy.load(), related=_RELATED)
    return result.obligations


def _print(stage: str, payload: dict) -> None:
    r = decide_deploy(payload)
    print(stage)
    print(f"   decision        : {r.decision}")
    if r.missing_artefacts:
        print(f"   missing         : {r.missing_artefacts}")
    if r.under_approved:
        print(f"   under-approved  : {r.under_approved}")
    for reason in r.reasons:
        print(f"   reason          : {reason}")
    print()
    return r.decision


def main() -> int:
    obligations = _obligations()
    print(f"Deploy gate — {_USE_CASE_ID} (offline)\n")
    print(f"Required obligations ({len(obligations)}): {', '.join(obligations)}\n")

    # 1. First attempt: nothing recorded.
    first = {
        "use_case_id": _USE_CASE_ID,
        "obligations": obligations,
        "artefacts": {k: None for k in obligations},
        "approvals": [],
    }
    _print("1. First deploy (no artefacts, no approvals)", first)

    # 2. Artefacts recorded + two distinct approvers each.
    approved = {
        "use_case_id": _USE_CASE_ID,
        "obligations": obligations,
        "artefacts": {k: f"docs/compliance/{k}.md" for k in obligations},
        "approvals": [
            {"artefact": "*", "approver": "compliance-officer"},
            {"artefact": "*", "approver": "engineering-lead"},
        ],
    }
    _print("2. After artefacts recorded and approved by two distinct people", approved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
