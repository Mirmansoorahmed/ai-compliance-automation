"""Guard against OPA merge conflicts in the policy-data directory.

OPA loads every ``policy/data/*.json`` file and merges them into one ``data``
document. If two files define the same top-level key, OPA fails at load time
with ``merge error: conflicting values at data.data.<key>`` and `opa test
policy` never runs. This test reproduces that merge offline: it collects the
top-level keys of every JSON file under ``policy/data/`` and fails if any key
is defined in more than one file — the same condition OPA rejects.

This is why the doc strings use file-unique keys (``_doc_thresholds``,
``_doc_element_margins``) instead of a shared ``_doc``.
"""

from __future__ import annotations

import json
from collections import defaultdict

from aca.paths import policy_data_dir


def test_policy_data_has_no_conflicting_top_level_keys():
    data_dir = policy_data_dir()
    json_files = sorted(data_dir.glob("*.json"))
    assert json_files, f"no policy-data JSON files found under {data_dir}"

    # top-level key -> list of files that define it
    key_sources: dict[str, list[str]] = defaultdict(list)
    for path in json_files:
        obj = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(obj, dict), f"{path.name} must be a JSON object at top level"
        for key in obj:
            key_sources[key].append(path.name)

    conflicts = {k: v for k, v in key_sources.items() if len(v) > 1}
    assert not conflicts, (
        "policy/data/*.json files share top-level keys, which OPA rejects when "
        "it merges them into one data document (merge error: conflicting values "
        f"at data.data.<key>): {conflicts}"
    )
