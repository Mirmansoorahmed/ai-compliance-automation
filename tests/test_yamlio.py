"""Phase 1 — minimal YAML reader tests."""

import pytest

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


def test_dates_load_as_strings_subset_path(tmp_path):
    # The dependency-free subset parser keeps dates as plain strings.
    p = tmp_path / "r.yaml"
    p.write_text("effective_from: 2026-11-14\nreview_by: 2027-11-14\n", encoding="utf-8")
    doc = load_yaml(p)
    assert doc["effective_from"] == "2026-11-14"
    assert isinstance(doc["effective_from"], str)
    assert isinstance(doc["review_by"], str)


def test_dates_load_as_strings_with_pyyaml_when_available():
    # If PyYAML is installed, loads_yaml must still return strings for dates,
    # so results are identical with and without PyYAML. Skips cleanly when the
    # optional dependency is absent (e.g. the offline oss sandbox).
    pyyaml = pytest.importorskip("yaml")
    import importlib

    from aca.register import yamlio as yamlio_mod

    importlib.reload(yamlio_mod)  # pick up PyYAML now that it is importable
    assert yamlio_mod._pyyaml is not None
    doc = yamlio_mod.loads_yaml("effective_from: 2026-11-14\n")
    assert doc["effective_from"] == "2026-11-14"
    assert isinstance(doc["effective_from"], str)
