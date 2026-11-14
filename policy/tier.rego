package compliance.tier

# OPA is the only decision point. The Semantic Guard emits labels; this policy
# maps labels + signed data (thresholds, confirmed patterns) to a single tier:
#   deny > four-eyes > ask > allow  (strictest matching outcome wins).
#
# Safety invariants:
# - `deny` is reachable ONLY when a label's pattern_id is in
#   data.confirmed_prohibited_patterns, which is populated only by an approved
#   `confirmed_prohibited_pattern` interpretation merged via PR + four-eyes.
# - thresholds and confirmed patterns come from signed data (policy/data),
#   never mutated at runtime.
#
# Input shape:
#   { "labels": [ {concept_id, pattern_id?, elements_met[], confidence}, ... ] }
#
# Illustrative mapping only; not a conformity claim.

import rego.v1

default tier := "allow"

# --- deny: a confirmed prohibited pattern matched ---
deny_match if {
	some l in input.labels
	l.pattern_id in data.confirmed_prohibited_patterns
}

# --- four-eyes: concept present at high confidence with enough elements met ---
four_eyes_match if {
	some l in input.labels
	th := data.thresholds[l.concept_id]
	l.confidence >= th.high
	count(l.elements_met) >= th.min_elements
}

# --- ask: concept present at or above the low threshold ---
ask_match if {
	some l in input.labels
	th := data.thresholds[l.concept_id]
	l.confidence >= th.low
}

tier := "deny" if {
	deny_match
}

tier := "four-eyes" if {
	not deny_match
	four_eyes_match
}

tier := "ask" if {
	not deny_match
	not four_eyes_match
	ask_match
}
