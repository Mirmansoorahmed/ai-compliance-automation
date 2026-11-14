"""Four-eyes review recorder (R9).

When a decision is `ask` / `four-eyes`, a named reviewer records an
interpretation (owner, reason, decision) and the eval cases that justify it.
The recorder turns that into a *change set* — an interpretation YAML plus eval
fixtures written to the working tree on a new branch — ready for a PR reviewed
by two distinct approvers (CODEOWNERS four-eyes).

Hard rule (R9.3): the recorder NEVER writes policy data (thresholds,
confirmed_prohibited_patterns) or mutates the register at runtime. It only
stages files for human review. A confirmed pattern becomes enforceable only
after the PR is merged and CI passes — i.e. by humans, not by the running
system. ``assert_no_policy_write`` enforces this against the staged paths.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from aca.review.yamlwrite import dump_mapping

INTERPRETATION_FIELDS = [
    "id",
    "version",
    "requirement_id",
    "decision",
    "owner",
    "reason",
    "effective_from",
    "review_by",
    "rule_ref",
    "eval_cases",
    "status",
]

# Paths the recorder must never write to at runtime (policy is PR + four-eyes).
_POLICY_PREFIXES = ("policy/",)


class PolicyWriteError(RuntimeError):
    """Raised if a review change set would write policy data at runtime."""


def assert_no_policy_write(paths: list[str]) -> None:
    offending = [p for p in paths if any(p.startswith(pre) for pre in _POLICY_PREFIXES)]
    if offending:
        raise PolicyWriteError(
            f"review change set must not write policy data at runtime: {offending}"
        )


@dataclass
class ReviewDecision:
    interpretation_id: str
    requirement_id: str
    decision: str  # confirmed_prohibited_pattern | not_in_scope | needs_review
    owner: str
    reason: str
    effective_from: str
    review_by: str
    version: int = 1
    status: str = "draft"
    rule_ref: str | None = None
    # eval cases to add, each a dict written to eval/cases/<name>.yaml
    eval_cases: list[dict] = field(default_factory=list)


@dataclass
class ChangeSet:
    branch: str
    interpretation_path: str
    eval_case_paths: list[str]
    files: dict[str, str]  # path -> content

    @property
    def all_paths(self) -> list[str]:
        return [self.interpretation_path, *self.eval_case_paths]


def build_change_set(decision: ReviewDecision, *, repo_root: Path | None = None) -> ChangeSet:
    """Build (but do not commit) the interpretation + eval-case files."""
    root = repo_root or Path.cwd()
    files: dict[str, str] = {}

    interp = {
        "id": decision.interpretation_id,
        "version": decision.version,
        "requirement_id": decision.requirement_id,
        "decision": decision.decision,
        "owner": decision.owner,
        "reason": decision.reason,
        "effective_from": decision.effective_from,
        "review_by": decision.review_by,
        "status": decision.status,
    }
    if decision.rule_ref:
        interp["rule_ref"] = decision.rule_ref

    eval_case_paths: list[str] = []
    for i, case in enumerate(decision.eval_cases, start=1):
        name = case.get("id") or f"{decision.interpretation_id}-case-{i}"
        rel = f"eval/cases/{name}.yaml"
        eval_case_paths.append(rel)
        files[rel] = dump_mapping(case)

    # Record which eval cases this interpretation introduced (FK validated by
    # the register validator in CI).
    if eval_case_paths:
        interp["eval_cases"] = eval_case_paths

    interp_path = f"interpretations/{decision.interpretation_id}.yaml"
    files[interp_path] = dump_mapping(interp, INTERPRETATION_FIELDS)

    assert_no_policy_write(list(files))

    branch = f"review/{decision.interpretation_id.lower()}"
    return ChangeSet(
        branch=branch,
        interpretation_path=interp_path,
        eval_case_paths=eval_case_paths,
        files=files,
    )


def write_change_set(change_set: ChangeSet, *, repo_root: Path) -> list[str]:
    """Write the change-set files to the working tree. Returns written paths."""
    assert_no_policy_write(list(change_set.files))
    written = []
    for rel, content in change_set.files.items():
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(rel)
    return written


def _run_git(args: list[str], *, repo_root: Path, runner=subprocess.run):
    return runner(["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True)


def stage_as_branch(
    change_set: ChangeSet,
    *,
    repo_root: Path,
    commit_message: str,
    base_branch: str = "spec",
    runner=subprocess.run,
    do_commit: bool = True,
) -> list[str]:
    """Create the review branch, write files, and commit them (no push).

    Pushing / opening the PR is left to the caller so the recorder stays
    offline-testable and never requires network. ``runner`` is injectable so
    tests can assert the git calls without executing them.
    """
    _run_git(["checkout", "-b", change_set.branch, base_branch], repo_root=repo_root, runner=runner)
    written = write_change_set(change_set, repo_root=repo_root)
    if do_commit:
        _run_git(["add", *written], repo_root=repo_root, runner=runner)
        _run_git(["commit", "-m", commit_message], repo_root=repo_root, runner=runner)
    return written
