package compliance.tier_test

import data.compliance.tier
import rego.v1

# Signed-data stand-ins for the tests below. Named `fixture_data` (not
# `test_data`) so `opa test` does not pick it up as a test rule. The deny branch
# requires a confirmed pattern; the production data file keeps this list empty
# until an approved confirmed_prohibited_pattern interpretation is merged via
# four-eyes.
fixture_data := {
	"thresholds": {"AIA-5-1-c": {"low": 0.45, "high": 0.8, "min_elements": 3}},
	"confirmed_prohibited_patterns": ["AIA-5-1-c/joined-behaviour-adverse-action"],
}

test_deny_on_confirmed_pattern if {
	tier.tier == "deny" with input as {"labels": [{
		"concept_id": "AIA-5-1-c",
		"pattern_id": "AIA-5-1-c/joined-behaviour-adverse-action",
		"elements_met": ["join", "score", "adverse"],
		"confidence": 0.9,
	}]}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}

# A full validated match — all elements present with elements_total set and a
# pattern_id, as the adapter emits for a full match — routes to four-eyes. The
# pattern_id here is NOT in the confirmed-prohibited list, so the outcome is
# four-eyes (a confirmed pattern_id would be deny — see test_deny_on_confirmed_pattern).
test_four_eyes_on_full_validated_match if {
	tier.tier == "four-eyes" with input as {"labels": [{
		"concept_id": "AIA-5-1-c",
		"pattern_id": "AIA-5-1-c/joined-behaviour-adverse-action-unconfirmed",
		"elements_met": ["join", "score", "adverse"],
		"elements_total": 3,
		"confidence": 0.85,
	}]}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}

# Fix #2: the SAME three elements WITHOUT a full validated match (no pattern_id,
# no elements_total) is ASK at most, not four-eyes — high confidence alone can
# never reach four-eyes.
test_same_elements_without_validated_match_is_ask if {
	tier.tier == "ask" with input as {"labels": [{
		"concept_id": "AIA-5-1-c",
		"elements_met": ["join", "score", "adverse"],
		"confidence": 0.85,
	}]}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}

# A full element match routes to four-eyes even at low similarity confidence.
test_four_eyes_on_full_elements_low_conf if {
	tier.tier == "four-eyes" with input as {"labels": [{
		"concept_id": "AIA-5-1-c",
		"elements_met": ["join", "score", "adverse"],
		"elements_total": 3,
		"confidence": 0.1,
	}]}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}

# A partial pattern (some-but-not-all elements) routes to ask even when the
# confidence is below the low threshold — never allow.
test_ask_on_partial_pattern_low_conf if {
	tier.tier == "ask" with input as {"labels": [{
		"concept_id": "AIA-5-1-c",
		"elements_met": ["join", "score"],
		"confidence": 0.1,
		"partial_pattern": true,
	}]}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}

test_ask_on_low_conf if {
	tier.tier == "ask" with input as {"labels": [{
		"concept_id": "AIA-5-1-c",
		"elements_met": ["join"],
		"confidence": 0.5,
	}]}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}

test_allow_when_below_low if {
	tier.tier == "allow" with input as {"labels": [{
		"concept_id": "AIA-5-1-c",
		"elements_met": [],
		"confidence": 0.1,
	}]}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}

test_allow_on_empty_labels if {
	tier.tier == "allow" with input as {"labels": []}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}

# High confidence but too few elements -> not four-eyes, falls to ask.
test_high_conf_few_elements_is_ask if {
	tier.tier == "ask" with input as {"labels": [{
		"concept_id": "AIA-5-1-c",
		"elements_met": ["join"],
		"confidence": 0.9,
	}]}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}

# Phase A: a similarity_only signal (no elements, no partial) routes to ASK.
test_ask_on_similarity_only if {
	tier.tier == "ask" with input as {"labels": [{
		"concept_id": "AIA-5-1-c",
		"elements_met": [],
		"elements_total": 3,
		"confidence": 0.6,
		"similarity_only": true,
	}]}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}

# Phase A invariant: similarity_only can NEVER reach four-eyes or deny, even at
# high confidence, because the full element match is absent.
test_similarity_only_never_blocks_at_high_conf if {
	tier.tier == "ask" with input as {"labels": [{
		"concept_id": "AIA-5-1-c",
		"elements_met": [],
		"elements_total": 3,
		"confidence": 0.99,
		"similarity_only": true,
	}]}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}

# Fix #2: similarity_only with 1..n-1 elements present AND high confidence must
# still be ASK — never four-eyes — because the FULL element match is absent.
test_similarity_only_with_partial_elements_high_conf_is_ask if {
	tier.tier == "ask" with input as {"labels": [{
		"concept_id": "AIA-5-1-c",
		"elements_met": ["join", "score"],
		"elements_total": 3,
		"confidence": 0.99,
		"similarity_only": true,
	}]}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}

# Fix #2: even if ALL elements appear met, a similarity_only label never reaches
# four-eyes — only a validated (non-similarity) full match does.
test_similarity_only_with_all_elements_is_still_ask_not_four_eyes if {
	tier.tier == "ask" with input as {"labels": [{
		"concept_id": "AIA-5-1-c",
		"elements_met": ["join", "score", "adverse"],
		"elements_total": 3,
		"confidence": 0.99,
		"similarity_only": true,
	}]}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}

# Fix #2: high confidence with enough elements but NO full match and NO
# similarity flag no longer reaches four-eyes (the confidence-only path is gone);
# it is ASK.
test_high_conf_partial_elements_no_full_match_is_ask if {
	tier.tier == "ask" with input as {"labels": [{
		"concept_id": "AIA-5-1-c",
		"elements_met": ["join", "score"],
		"elements_total": 3,
		"confidence": 0.95,
	}]}
		with data.thresholds as fixture_data.thresholds
		with data.confirmed_prohibited_patterns as fixture_data.confirmed_prohibited_patterns
}
