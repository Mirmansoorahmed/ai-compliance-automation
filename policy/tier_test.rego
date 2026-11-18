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

test_four_eyes_on_high_conf_enough_elements if {
	tier.tier == "four-eyes" with input as {"labels": [{
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
