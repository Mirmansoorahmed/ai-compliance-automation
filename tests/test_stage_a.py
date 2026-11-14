"""Phase 4 — stage A artefact/diff analysis tests (R3.6)."""

from aca.guard.stages.stage_a import run_stage_a

SOCIAL_SCORING_DIFF = """
+def build_reliability_index(df):
+    merged = badge_logs.merge(slack_activity, on='employee_id')
+    merged = merged.merge(canteen_purchases, on='employee_id')
+    merged['reliability_index'] = score(merged)
+    bottom = merged.sort_values('reliability_index').head(int(0.1 * len(merged)))
+    remove_from_bonus_pool(bottom['employee_id'])
"""

BENIGN_DIFF = """
+def fraud_score(transactions):
+    return model.predict(transactions[['amount', 'merchant', 'country']])
"""


def test_social_scoring_diff_flags_all_three_elements():
    r = run_stage_a(SOCIAL_SCORING_DIFF)
    assert r.has_person_join
    assert r.behaviour_source_count >= 2
    assert r.has_aggregated_score
    assert r.has_adverse_action
    assert r.all_elements
    assert set(r.elements_met) == {
        "person_identifiable_behaviour_join",
        "aggregated_score_or_ranking",
        "adverse_action",
    }


def test_benign_diff_does_not_flag_all_elements():
    r = run_stage_a(BENIGN_DIFF)
    assert not r.all_elements
    assert "adverse_action" not in r.elements_met
