"""guardrails-ci CLI — the Phase 3 CI gate.

    guardrails-ci [--base REF] [--head REF] [--diff-file PATH]
                  [--repo DIR] [--use-case PATH]
                  [--report PATH] [--aibom PATH] [--ask-passes]

Reads the diff (git refs ``base...head``, default ``origin/main...HEAD``, or a
``--diff-file`` for fixtures), runs the local secret scan + the /v1/check
decision engine in-process + the optional external scanners, writes
``ci-report.md`` and ``ai-bom.json``, and exits with the gate code:

  BLOCK -> 1   (check fails)
  ASK   -> 1   (unless --ask-passes, then 0)
  WARN  -> 0
  ALLOW -> 0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from guardrails_ci import aibom as aibom_mod
from guardrails_ci import diff as diff_mod
from guardrails_ci import report as report_mod
from guardrails_ci import tools as tools_mod
from guardrails_ci import usecase as usecase_mod
from guardrails_ci.engine import evaluate

DEFAULT_BASE = "origin/main"
DEFAULT_HEAD = "HEAD"


def _exit_code(decision: str, *, ask_passes: bool) -> int:
    if decision == "BLOCK":
        return 1
    if decision == "ASK":
        return 0 if ask_passes else 1
    return 0  # WARN, ALLOW


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="guardrails-ci", description="EU AI compliance CI gate.")
    p.add_argument("--base", default=DEFAULT_BASE, help="base git ref (default origin/main)")
    p.add_argument("--head", default=DEFAULT_HEAD, help="head git ref (default HEAD)")
    p.add_argument("--diff-file", help="read the unified diff from a file instead of git")
    p.add_argument("--repo", default=".", help="repo root (for use-case.yaml and git)")
    p.add_argument("--use-case", help="explicit path to use-case.yaml (overrides repo default)")
    p.add_argument("--report", default="ci-report.md", help="output path for the markdown report")
    p.add_argument("--aibom", default="ai-bom.json", help="output path for the AI-BOM JSON")
    p.add_argument("--ask-passes", action="store_true", help="treat an ASK decision as a pass (exit 0)")
    p.add_argument("--quiet", action="store_true", help="do not print the report to stdout")
    return p


def run(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)

    # 1. Diff.
    if args.diff_file:
        diff = diff_mod.diff_from_file(args.diff_file)
    else:
        try:
            diff = diff_mod.diff_from_refs(args.base, args.head, repo=args.repo)
        except Exception as exc:  # git missing / bad ref -> fail safe to ASK path
            sys.stderr.write(f"guardrails-ci: could not read git diff ({exc}); "
                             "pass --diff-file or check the refs.\n")
            return 1

    # 2. Use case.
    use_case = usecase_mod.load_use_case(args.repo, explicit=args.use_case)
    use_case_id = use_case.get("id") if isinstance(use_case, dict) else None

    # 3. Decision engine (in-process) + optional external scanners.
    result = evaluate(diff, use_case)
    scanners = tools_mod.run_optional_tools(diff.changed_paths)

    # 4. Outputs.
    report_text = report_mod.render_report(
        result, tools=scanners, changed_paths=diff.changed_paths, use_case_id=use_case_id)
    Path(args.report).write_text(report_text, encoding="utf-8")

    bom = aibom_mod.build_aibom()
    Path(args.aibom).write_text(json.dumps(bom, indent=2) + "\n", encoding="utf-8")

    if not args.quiet:
        sys.stdout.write(report_text)

    return _exit_code(result.decision, ask_passes=args.ask_passes)


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
