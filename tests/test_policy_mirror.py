"""Phase 2 — Python mirror of the OPA tier policy (R6).

These cases mirror policy/tier_test.rego one-for-one so the decision logic is
verified in pytest even when the `opa` binary is unavailable. policy/tier.rego
is authoritative; a divergence here is a bug.
"""

import pytest

from aca.policy.decide import PolicyData, decide, load_policy_data

TEST_DATA = PolicyData(
    thresholds={"AIA-5-1-c": {"low": 0.45, "high": 0.8, "min_elements": 3}},
    confirmed_prohibited_patterns=["AIA-5-1-c/joined-behaviour-adverse-action"],
)


def test_deny_on_confirmed_pattern():
    labels = [{
        "concept_id": "AIA-5-1-c",
        "pattern_id": "AIA-5-1-c/joined-behaviour-adverse-action",
        "elements_met": ["join", "score", "adverse"],
        "confidence": 0.9,
    }]
    assert decide(labels, TEST_DATA) == "deny"


def test_four_eyes_on_high_conf_enough_elements():
    labels = [{
        "concept_id": "AIA-5-1-c",
        "elements_met": ["join", "score", "adverse"],
        "confidence": 0.85,
    }]
    assert decide(labels, TEST_DATA) == "four-eyes"


def test_ask_on_low_conf():
    labels = [{"concept_id": "AIA-5-1-c", "elements_met": ["join"], "confidence": 0.5}]
    assert decide(labels, TEST_DATA) == "ask"


def test_allow_when_below_low():
    labels = [{"concept_id": "AIA-5-1-c", "elements_met": [], "confidence": 0.1}]
    assert decide(labels, TEST_DATA) == "allow"


def test_allow_on_empty_labels():
    assert decide([], TEST_DATA) == "allow"


def test_high_conf_few_elements_is_ask():
    labels = [{"concept_id": "AIA-5-1-c", "elements_met": ["join"], "confidence": 0.9}]
    assert decide(labels, TEST_DATA) == "ask"


def test_strictest_outcome_wins_across_labels():
    labels = [
        {"concept_id": "AIA-5-1-c", "elements_met": ["join"], "confidence": 0.5},  # ask
        {
            "concept_id": "AIA-5-1-c",
            "pattern_id": "AIA-5-1-c/joined-behaviour-adverse-action",
            "elements_met": ["join", "score", "adverse"],
            "confidence": 0.9,
        },  # deny
    ]
    assert decide(labels, TEST_DATA) == "deny"


def test_production_data_has_no_confirmed_patterns_yet():
    # Until an approved confirmed_prohibited_pattern interpretation is merged
    # (Phase 7, four-eyes), the signed data must not enable any auto-deny.
    data = load_policy_data()
    assert data.confirmed_prohibited_patterns == []


def test_unknown_concept_ignored():
    labels = [{"concept_id": "UNKNOWN", "elements_met": ["x"], "confidence": 0.99}]
    assert decide(labels, TEST_DATA) == "allow"
