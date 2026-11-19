"""Demo: run the CI gate over the two committed fixtures, offline (Phase 3).

For each fixture it prints the decision, the gate exit code, and the pending
obligations checklist, so you can see:

  - secret.diff     -> BLOCK, exit 1 (a hardcoded test credential fails the gate)
  - cv-feature.diff -> WARN,  exit 0 (the CV feature passes but lists the real
                                      missing artefacts; count comes from the catalog)

Fully offline (hashed-fallback embedder, no model download). The obligation
count is whatever the catalog yields — nothing is hardcoded.
"""

from __future__ import annotations

from pathlib import Path

from guardrails_ci import diff as diff_mod
from guardrails_ci import tools as tools_mod
from guardrails_ci import usecase as usecase_mod
from guardrails_ci.cli import _exit_code
from guardrails_ci.engine import build_check_service, evaluate

_FIX = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ci"

_CASES = [
    {"name": "1. Hardcoded test credential (secret.diff)",
     "diff": _FIX / "secret.diff", "use_case": None},
    {"name": "2. CV screening feature (cv-feature.diff)",
     "diff": _FIX / "cv-feature.diff", "use_case": _FIX / "use-case-cv.yaml"},
]


def main() -> int:
    service = build_check_service()
    print("guardrails-ci demo — two fixtures through the CI gate (offline)\n")
    for case in _CASES:
        diff = diff_mod.diff_from_file(case["diff"])
        use_case = usecase_mod.load_use_case(explicit=case["use_case"]) if case["use_case"] else None
        result = evaluate(diff, use_case, service=service)
        code = _exit_code(result.decision, ask_passes=False)
        scanners = tools_mod.run_optional_tools(diff.changed_paths)

        print(case["name"])
        print(f"   decision  : {result.decision}")
        print(f"   exit code : {code}")
        check_ids = ", ".join(result.check_ids) if result.check_ids else "(none)"
        print(f"   rules     : {check_ids}")
        if result.obligations:
            print(f"   obligations ({len(result.obligations)}, pending checklist):")
            missing = set(result.missing_artefacts)
            for key in result.obligations:
                box = "[ ]" if key in missing else "[x]"
                print(f"      {box} {key} ({'missing' if key in missing else 'present'})")
        scanner_status = ", ".join(f"{t.name}={t.status}" for t in scanners)
        print(f"   scanners  : {scanner_status}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
