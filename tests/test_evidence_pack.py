"""Phase 7 — evidence pack v2: trace, mapping, cleanliness, fail-closed."""

import pytest

from aca.evidence_pack.collect import build_trace, mapping_table
from aca.evidence_pack.render import (
    EvidencePackError,
    assert_clean,
    render_text,
)


def test_trace_covers_all_four_enforcement_points():
    trace = build_trace()
    points = {p.point for p in trace.points}
    assert points == {"editor", "ci", "deploy", "runtime"}


def test_trace_tells_deny_then_allow_at_deploy():
    trace = build_trace()
    deploys = [p for p in trace.points if p.point == "deploy"]
    assert [d.decision for d in deploys] == ["DENY", "ALLOW"]


def test_trace_has_social_block_and_secret_block():
    trace = build_trace()
    decisions = [(p.point, p.decision, tuple(p.rules)) for p in trace.points]
    assert any(d == "BLOCK" and "AIA-5-1-c" in r for _, d, r in decisions)
    assert any(d == "BLOCK" and "SEC-SECRETS" in r for _, d, r in decisions)


def test_trace_has_obligations_and_two_approvals():
    trace = build_trace()
    assert trace.obligations
    assert len(trace.approvals) == 2
    roles = {a["approver_role"] for a in trace.approvals}
    assert len(roles) == 2  # two distinct people


def test_mapping_table_links_iso_and_act():
    rows = mapping_table()
    assert rows
    for r in rows:
        assert r["control"] and r["enforced_at"]


def test_rendered_pack_is_clean_of_code_paths_hashes():
    text = render_text(build_trace())
    # render_text calls assert_clean; re-assert here for clarity.
    assert_clean(text)
    assert "Evidence Pack (v2)" in text
    assert "Decision trace" in text
    assert "mapping" in text.lower()


def test_assert_clean_rejects_paths():
    with pytest.raises(EvidencePackError):
        assert_clean("see src/aca/report/build.py for details")


def test_assert_clean_rejects_hashes():
    with pytest.raises(EvidencePackError):
        assert_clean("commit 9617ae9de8ef verifies this")


def test_assert_clean_rejects_code_blocks():
    with pytest.raises(EvidencePackError):
        assert_clean("here is code:\n```\nx = 1\n```")


def test_build_writes_pdf(tmp_path):
    from aca.evidence_pack.build import build_evidence_pack
    out = tmp_path / "pack.pdf"
    path = build_evidence_pack(out_path=out)
    assert path.exists()
    assert path.read_bytes().startswith(b"%PDF")
