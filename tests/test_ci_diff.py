"""Phase 3 — unified-diff parsing for the CI gate."""

from pathlib import Path

from guardrails_ci.diff import parse_diff, diff_from_file

_FIX = Path(__file__).resolve().parent / "fixtures" / "ci"


def test_parse_added_lines_and_paths():
    diff = diff_from_file(_FIX / "secret.diff")
    assert diff.changed_paths == ["src/config/aws.py"]
    f = diff.file("src/config/aws.py")
    assert f is not None
    assert any("AKIA" in line for line in f.added_lines)
    # The +++ header itself is not counted as an added line.
    assert all(not line.startswith("+++") for line in f.added_lines)


def test_cv_feature_has_two_files():
    diff = diff_from_file(_FIX / "cv-feature.diff")
    assert set(diff.changed_paths) == {"src/hr/cv_screening.py", ".guardrails/use-case.yaml"}


def test_deleted_file_is_ignored():
    text = (
        "diff --git a/old.py b/old.py\n"
        "--- a/old.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-gone = 1\n"
    )
    diff = parse_diff(text)
    assert diff.changed_paths == []


def test_removed_lines_not_counted():
    text = (
        "diff --git a/f.py b/f.py\n"
        "--- a/f.py\n"
        "+++ b/f.py\n"
        "@@ -1 +1 @@\n"
        "-old = 1\n"
        "+new = 2\n"
    )
    diff = parse_diff(text)
    f = diff.file("f.py")
    assert f.added_lines == ["new = 2"]


def test_added_text_joins_all_files():
    diff = diff_from_file(_FIX / "cv-feature.diff")
    assert "score_applicants" in diff.added_text
    assert "uc-hr-cv-screening" in diff.added_text
