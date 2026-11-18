"""Phase 1 — the demo makes the four calls and prints the right decisions."""

from aca.check.demo import build_service, _CASES


def test_demo_four_decisions():
    svc = build_service()
    decisions = {}
    for case in _CASES:
        out = svc.check(case["payload"])
        decisions[case["name"]] = out["decision"]
    assert decisions["1. CV screening (Annex III 4(a))"] == "WARN"
    assert decisions["2. Social scoring (Art. 5(1)(c))"] == "BLOCK"
    assert decisions["3. Fraud score (objective facts)"] == "ALLOW"
    assert decisions["4. Secret pasted into a diff"] == "BLOCK"
