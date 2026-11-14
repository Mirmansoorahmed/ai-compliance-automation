"""Phase 1 — minimal YAML reader tests."""

from aca.register.yamlio import load_yaml


def test_reads_scalars_and_list(tmp_path):
    p = tmp_path / "r.yaml"
    p.write_text(
        "id: REQ-X\n"
        "count: 3\n"
        "flag: true\n"
        "empty: null\n"
        "title: Social scoring of natural persons\n"
        "elements:\n"
        "  - first element\n"
        "  - second element\n",
        encoding="utf-8",
    )
    doc = load_yaml(p)
    assert doc["id"] == "REQ-X"
    assert doc["count"] == 3
    assert doc["flag"] is True
    assert doc["empty"] is None
    assert doc["elements"] == ["first element", "second element"]


def test_strips_comments_and_blank_lines(tmp_path):
    p = tmp_path / "r.yaml"
    p.write_text(
        "# a comment\n"
        "\n"
        "id: REQ-Y  # trailing comment\n"
        "mode: auto\n",
        encoding="utf-8",
    )
    doc = load_yaml(p)
    assert doc == {"id": "REQ-Y", "mode": "auto"}


def test_quoted_values_preserved(tmp_path):
    p = tmp_path / "r.yaml"
    p.write_text('citation: "Art. 5(1)(c)"\n', encoding="utf-8")
    doc = load_yaml(p)
    assert doc["citation"] == "Art. 5(1)(c)"
