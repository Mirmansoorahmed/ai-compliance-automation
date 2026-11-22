"""Phase 3 — .guardrails/ignore support for the CI gate.

Excluded paths are dropped before the secret scan and /v1/check, so the gate
does not BLOCK on the repo's own deliberate-bad test corpus. The exclusion must
never weaken the gate for real code: a secret in an excluded fixture is not a
BLOCK, but the same secret under src/ still BLOCKs. A change to the ignore file
itself is always scanned and reported.
"""

from pathlib import Path

import pytest

from guardrails_ci import diff as diff_mod
from guardrails_ci import ignore as ignore_mod
from guardrails_ci.cli import run
from guardrails_ci.engine import build_check_service, evaluate
from guardrails_ci.report import render_report

_SECRET_LINE = 'AWS_ACCESS_KEY_ID = "AKIAXXXXXXXXXXXXXXXX"'


@pytest.fixture(scope="module")
def service():
    return build_check_service()


def _diff_for(path: str, line: str) -> diff_mod.Diff:
    text = (
        f"diff --git a/{path} b/{path}\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        f"+++ b/{path}\n"
        "@@ -0,0 +1,1 @@\n"
        f"+{line}\n"
    )
    return diff_mod.parse_diff(text)


# --- parsing + matching -------------------------------------------------------

def test_parse_skips_comments_and_blanks():
    text = "# a comment\n\n  \neval/tuning_v2/**\n#another\ntests/fixtures/ci/secret.diff\n"
    pats = ignore_mod.parse_patterns(text)
    assert pats == ["eval/tuning_v2/**", "tests/fixtures/ci/secret.diff"]


def test_match_dir_doublestar():
    spec = ignore_mod.IgnoreSpec(patterns=["eval/tuning_v2/**"], present=True)
    assert spec.matches("eval/tuning_v2/aia-5-1-c-pos-en-01.yaml")
    assert spec.matches("eval/tuning_v2/sub/x.yaml")
    assert not spec.matches("eval/heldout_v2/x.yaml")
    assert not spec.matches("src/aca/check/demo.py")


def test_match_nested_doublestar_glob():
    spec = ignore_mod.IgnoreSpec(
        patterns=["tests/fixtures/hooks/**/tool-write-secret.json"], present=True)
    assert spec.matches("tests/fixtures/hooks/claude/tool-write-secret.json")
    assert spec.matches("tests/fixtures/hooks/kiro/tool-write-secret.json")
    assert not spec.matches("tests/fixtures/hooks/claude/prompt-social.json")


def test_exact_file_match():
    spec = ignore_mod.IgnoreSpec(patterns=["tests/fixtures/ci/secret.diff"], present=True)
    assert spec.matches("tests/fixtures/ci/secret.diff")
    assert not spec.matches("tests/fixtures/ci/cv-feature.diff")


def test_never_excludes_src_or_policy():
    # Even a pattern that would match src/ is a mistake; but the committed file
    # must not contain one. Here we assert the matcher does not over-reach.
    spec = ignore_mod.IgnoreSpec(patterns=["eval/**", "tests/fixtures/**"], present=True)
    assert not spec.matches("src/aca/check/secrets.py")
    assert not spec.matches("policy/catalog/catalog.yaml")
    assert not spec.matches("adapters/cursor/rules/eu-ai-compliance.mdc")
    assert not spec.matches(".github/workflows/ci.yml")


def test_ignore_file_itself_never_excluded():
    # A (mis)pattern that would match the ignore file must not exclude it.
    spec = ignore_mod.IgnoreSpec(patterns=[".guardrails/**", ".guardrails/ignore"], present=True)
    assert not spec.matches(".guardrails/ignore")


def test_ignore_file_changed_detection():
    assert ignore_mod.ignore_file_changed([".guardrails/ignore", "src/x.py"])
    assert ignore_mod.ignore_file_changed(["./.guardrails/ignore"])
    assert not ignore_mod.ignore_file_changed(["src/x.py", "eval/y.yaml"])


def test_partition_preserves_order():
    spec = ignore_mod.IgnoreSpec(patterns=["eval/**"], present=True)
    kept, excl = ignore_mod.partition_paths(
        ["src/a.py", "eval/b.yaml", "src/c.py", "eval/d.yaml"], spec)
    assert kept == ["src/a.py", "src/c.py"]
    assert excl == ["eval/b.yaml", "eval/d.yaml"]


# --- behaviour: the three point-4 guarantees ---------------------------------

def test_secret_in_excluded_fixture_gives_no_block(service):
    """A secret in an excluded path is dropped before the scan -> no BLOCK."""
    path = "eval/tuning_v2/leak.yaml"
    diff = _diff_for(path, _SECRET_LINE)
    spec = ignore_mod.IgnoreSpec(patterns=["eval/tuning_v2/**"], present=True)
    kept, excl = ignore_mod.partition_paths(diff.changed_paths, spec)
    assert excl == [path]
    result = evaluate(diff.keeping(kept), None, service=service)
    assert result.local_secret is False
    assert "SEC-SECRETS" not in result.check_ids
    assert result.decision != "BLOCK"


def test_same_secret_in_src_still_blocks(service):
    """The identical secret under src/ is NOT excluded -> still BLOCK."""
    path = "src/config/aws.py"
    diff = _diff_for(path, _SECRET_LINE)
    spec = ignore_mod.IgnoreSpec(patterns=["eval/tuning_v2/**"], present=True)
    kept, excl = ignore_mod.partition_paths(diff.changed_paths, spec)
    assert excl == []
    assert kept == [path]
    result = evaluate(diff.keeping(kept), None, service=service)
    assert result.local_secret is True
    assert "SEC-SECRETS" in result.check_ids
    assert result.decision == "BLOCK"


def test_ignore_file_change_is_reported(service):
    """A PR that touches .guardrails/ignore is flagged in the report."""
    diff = _diff_for(".guardrails/ignore", "eval/new_dir/**")
    spec = ignore_mod.IgnoreSpec(patterns=["eval/tuning_v2/**"], present=True)
    kept, excl = ignore_mod.partition_paths(diff.changed_paths, spec)
    # The ignore file is scanned, never excluded.
    assert ".guardrails/ignore" in kept
    assert excl == []
    changed = ignore_mod.ignore_file_changed(diff.changed_paths)
    assert changed is True
    result = evaluate(diff.keeping(kept), None, service=service)
    md = render_report(result, tools=[], changed_paths=kept,
                       excluded_paths=excl, ignore_changed=changed)
    assert ".guardrails/ignore" in md
    assert "changes `.guardrails/ignore`" in md


def test_report_lists_excluded_paths(service):
    diff = _diff_for("eval/tuning_v2/leak.yaml", _SECRET_LINE)
    spec = ignore_mod.IgnoreSpec(patterns=["eval/tuning_v2/**"], present=True)
    kept, excl = ignore_mod.partition_paths(diff.changed_paths, spec)
    result = evaluate(diff.keeping(kept), None, service=service)
    md = render_report(result, tools=[], changed_paths=kept, excluded_paths=excl)
    assert "Excluded paths (by .guardrails/ignore)" in md
    assert "eval/tuning_v2/leak.yaml" in md


# --- CLI wiring: excluded fixture does not fail the gate ----------------------

def test_cli_uses_repo_ignore_file(tmp_path, monkeypatch):
    """An excluded secret fixture under a repo with .guardrails/ignore -> exit 0;
    a src/ secret in the same repo would still exit 1 (gate not weakened)."""
    repo = tmp_path
    (repo / ".guardrails").mkdir()
    (repo / ".guardrails" / "ignore").write_text("eval/tuning_v2/**\n", encoding="utf-8")

    excluded_diff = repo / "excluded.diff"
    excluded_diff.write_text(
        "diff --git a/eval/tuning_v2/leak.yaml b/eval/tuning_v2/leak.yaml\n"
        "--- /dev/null\n+++ b/eval/tuning_v2/leak.yaml\n@@ -0,0 +1,1 @@\n"
        f"+{_SECRET_LINE}\n", encoding="utf-8")
    code = run(["--diff-file", str(excluded_diff), "--repo", str(repo),
                "--report", str(repo / "r1.md"), "--aibom", str(repo / "b1.json"),
                "--quiet"])
    assert code == 0, "secret in excluded fixture must not fail the gate"
    assert "Excluded paths" in (repo / "r1.md").read_text()

    src_diff = repo / "src.diff"
    src_diff.write_text(
        "diff --git a/src/config/aws.py b/src/config/aws.py\n"
        "--- /dev/null\n+++ b/src/config/aws.py\n@@ -0,0 +1,1 @@\n"
        f"+{_SECRET_LINE}\n", encoding="utf-8")
    code = run(["--diff-file", str(src_diff), "--repo", str(repo),
                "--report", str(repo / "r2.md"), "--aibom", str(repo / "b2.json"),
                "--quiet"])
    assert code == 1, "secret in src/ must still fail the gate"
