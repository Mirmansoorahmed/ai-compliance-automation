"""Phase 3 — the CI gate: decisions, exit codes, report, checklist, AI-BOM.

Runs fully offline (hashed-fallback embedder; no model download). The secret
fixture must BLOCK (exit 1); the CV fixture must WARN (exit 0) and list the
catalog's real missing artefacts — the count is asserted against the catalog,
never hardcoded.
"""

import json
from pathlib import Path

import pytest

from guardrails_ci import diff as diff_mod
from guardrails_ci import tools as tools_mod
from guardrails_ci import usecase as usecase_mod
from guardrails_ci.aibom import build_aibom
from guardrails_ci.cli import _exit_code, run
from guardrails_ci.engine import build_check_service, evaluate
from guardrails_ci.report import render_report
from guardrails_ci.tools import ToolResult

_FIX = Path(__file__).resolve().parent / "fixtures" / "ci"


@pytest.fixture(scope="module")
def service():
    return build_check_service()


# --- decisions + exit codes ---------------------------------------------------

def test_secret_blocks(service):
    diff = diff_mod.diff_from_file(_FIX / "secret.diff")
    result = evaluate(diff, None, service=service)
    assert result.decision == "BLOCK"
    assert "SEC-SECRETS" in result.check_ids
    assert result.local_secret is True
    assert _exit_code(result.decision, ask_passes=False) == 1


def test_cv_feature_warns(service):
    diff = diff_mod.diff_from_file(_FIX / "cv-feature.diff")
    uc = usecase_mod.load_use_case(explicit=_FIX / "use-case-cv.yaml")
    result = evaluate(diff, uc, service=service)
    assert result.decision == "WARN"
    assert "AIA-A3-4a" in result.check_ids
    assert _exit_code(result.decision, ask_passes=False) == 0


def test_exit_code_mapping():
    assert _exit_code("BLOCK", ask_passes=False) == 1
    assert _exit_code("WARN", ask_passes=False) == 0
    assert _exit_code("ALLOW", ask_passes=False) == 0
    assert _exit_code("ASK", ask_passes=False) == 1
    assert _exit_code("ASK", ask_passes=True) == 0


# --- artefact checklist (real catalog count, all missing) --------------------

def test_cv_checklist_matches_catalog_obligations(service):
    diff = diff_mod.diff_from_file(_FIX / "cv-feature.diff")
    uc = usecase_mod.load_use_case(explicit=_FIX / "use-case-cv.yaml")
    result = evaluate(diff, uc, service=service)
    # The obligations come from the catalog for Annex III 4(a); every artefact
    # path is null in the fixture, so all are missing.
    assert result.obligations  # non-empty
    assert set(result.missing_artefacts) == set(result.obligations)
    # 4(a) does not pull in a FRIA (that is the credit/insurance 5(b) path).
    assert "fria" not in result.obligations
    assert "worker_information" in result.obligations


def test_present_artefact_not_listed_missing(service):
    diff = diff_mod.diff_from_file(_FIX / "cv-feature.diff")
    uc = usecase_mod.load_use_case(explicit=_FIX / "use-case-cv.yaml")
    uc = dict(uc)
    uc["artefacts"] = dict(uc["artefacts"])
    uc["artefacts"]["dpia"] = "docs/compliance/dpia-cv.md"
    result = evaluate(diff, uc, service=service)
    assert "dpia" in result.obligations
    assert "dpia" not in result.missing_artefacts


# --- report content -----------------------------------------------------------

def test_report_has_decision_rules_and_checklist(service):
    diff = diff_mod.diff_from_file(_FIX / "cv-feature.diff")
    uc = usecase_mod.load_use_case(explicit=_FIX / "use-case-cv.yaml")
    result = evaluate(diff, uc, service=service)
    scanners = [ToolResult("gitleaks", "skipped", "not installed"),
                ToolResult("semgrep", "skipped", "not installed")]
    md = render_report(result, tools=scanners, changed_paths=diff.changed_paths,
                       use_case_id="uc-hr-cv-screening")
    assert "WARN" in md
    assert "AIA-A3-4a" in md
    assert "Annex III" in md            # legal reference travels with the rule
    assert "Pending obligations" in md
    assert "[ ] **worker_information**" in md
    assert f"requires {len(result.obligations)} artefact" in md
    assert "Halvaro Payments GmbH" in md


def test_secret_report_names_the_local_scan(service):
    diff = diff_mod.diff_from_file(_FIX / "secret.diff")
    result = evaluate(diff, None, service=service)
    md = render_report(result, tools=[], changed_paths=diff.changed_paths)
    assert "BLOCK" in md
    assert "SEC-SECRETS" in md
    assert "secret" in md.lower()


# --- missing-tool skip --------------------------------------------------------

def test_optional_tools_skip_when_not_installed(monkeypatch):
    # Neither binary on PATH -> both skipped, never an error, never a failure.
    monkeypatch.setattr(tools_mod.shutil, "which", lambda name: None)
    results = tools_mod.run_optional_tools(["a.py"])
    by_name = {t.name: t for t in results}
    assert by_name["gitleaks"].status == "skipped"
    assert by_name["semgrep"].status == "skipped"
    assert all(t.installed is False for t in results)


# --- AI-BOM shape -------------------------------------------------------------

def test_aibom_is_cyclonedx_with_provenance():
    bom = build_aibom()
    assert bom["bomFormat"] == "CycloneDX"
    assert bom["specVersion"]
    assert bom["components"]
    # Every component marks its provenance (declared vs guessed-from-docs).
    for comp in bom["components"]:
        provs = [p["value"] for p in comp["properties"] if p["name"] == "guardrails:provenance"]
        assert provs and provs[0] in ("declared", "declared-in-docs", "guessed")
    names = [c["name"] for c in bom["components"]]
    assert any("MiniLM" in n for n in names)          # the embedding model
    assert any("HashedEmbedder" in n for n in names)  # the fallback embedder


def test_aibom_model_version_has_no_operator():
    bom = build_aibom()
    model = next(c for c in bom["components"] if "MiniLM" in c["name"])
    assert not model["version"].startswith("==")


# --- CLI end to end -----------------------------------------------------------

def test_cli_secret_writes_outputs_and_exits_1(tmp_path):
    report = tmp_path / "ci-report.md"
    bom = tmp_path / "ai-bom.json"
    code = run(["--diff-file", str(_FIX / "secret.diff"),
                "--report", str(report), "--aibom", str(bom), "--quiet"])
    assert code == 1
    assert "BLOCK" in report.read_text()
    assert json.loads(bom.read_text())["bomFormat"] == "CycloneDX"


def test_cli_cv_exits_0_with_checklist(tmp_path):
    report = tmp_path / "ci-report.md"
    bom = tmp_path / "ai-bom.json"
    code = run(["--diff-file", str(_FIX / "cv-feature.diff"),
                "--use-case", str(_FIX / "use-case-cv.yaml"),
                "--report", str(report), "--aibom", str(bom), "--quiet"])
    assert code == 0
    text = report.read_text()
    assert "WARN" in text
    assert "Pending obligations" in text
