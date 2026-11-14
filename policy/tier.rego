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

# --- four-eyes: a full legal-element match, OR concept present at high
# confidence with enough elements. A full element match routes to four-eyes
# regardless of similarity confidence — the elements themselves are the signal,
# so a correctly-detected attack is never allowed on a low embedding score. ---
four_eyes_match if {
	some l in input.labels
	l.elements_total
	count(l.elements_met) >= l.elements_total
}

four_eyes_match if {
	some l in input.labels
	th := data.thresholds[l.concept_id]
	l.confidence >= th.high
	count(l.elements_met) >= th.min_elements
}

# --- ask: concept present at or above the low threshold, OR a partial pattern
# (some-but-not-all legal elements). A partial pattern always routes to a human
# review, never to allow, regardless of confidence. ---
ask_match if {
	some l in input.labels
	th := data.thresholds[l.concept_id]
	l.confidence >= th.low
}

ask_match if {
	some l in input.labels
	l.partial_pattern == true
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
