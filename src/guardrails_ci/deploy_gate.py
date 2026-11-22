"""guardrails-deploy-gate — the Phase 4 pre-deploy check (CLI).

Reads a use-case.yaml, resolves the feature's required obligations from the
catalog (same engine the CI gate uses), then applies the deploy gate
(policy/deploy.rego mirror): every required artefact present AND approved by two
distinct people. Exit 0 = ALLOW (deploy may proceed), exit 1 = DENY.

    guardrails-deploy-gate --use-case .guardrails/use-case.yaml

Used by the GitHub deploy workflow's gate job, which runs before the protected
``production`` environment. Stdlib only on the oss profile.
"""

from __future__ import annotations

import argparse
import sys

from aca.check.decide import CheckPolicy, decide_checks
from aca.check.deploy import decide_deploy
from aca.check.detectors import ANNEX_III_AREA_TO_CHECK, ANNEX_III_RELATED

from guardrails_ci import usecase as usecase_mod


def _obligations_for(use_case: dict) -> list[str]:
    fired: list[str] = []
    related: list[str] = []
    for area in use_case.get("annex_iii", []) or []:
        cid = ANNEX_III_AREA_TO_CHECK.get(str(area))
        if not cid:
            continue
        fired.append(cid)
        related.extend(ANNEX_III_RELATED.get(cid, []))
    result = decide_checks(fired, CheckPolicy.load(), related=related, use_case=use_case)
    return result.obligations


def run(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="guardrails-deploy-gate")
    p.add_argument("--use-case", required=True, help="path to use-case.yaml")
    p.add_argument("--repo", default=".", help="repo root (unused if --use-case is absolute)")
    args = p.parse_args(argv)

    use_case = usecase_mod.load_use_case(args.repo, explicit=args.use_case)
    if use_case is None:
        sys.stderr.write(f"guardrails-deploy-gate: could not read {args.use_case}\n")
        return 1

    obligations = _obligations_for(use_case)
    payload = {
        "use_case_id": use_case.get("id"),
        "obligations": obligations,
        "artefacts": use_case.get("artefacts") or {},
        "approvals": use_case.get("approvals") or [],
        "break_glass": use_case.get("break_glass") or {},
    }
    result = decide_deploy(payload)

    print(f"Deploy gate for {payload['use_case_id']}: {result.decision}")
    for reason in result.reasons:
        print(f"  - {reason}")
    return 0 if result.decision == "ALLOW" else 1


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
