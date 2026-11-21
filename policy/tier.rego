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
#   { "labels": [ {concept_id, pattern_id?, elements_met[], confidence,
#                  partial_pattern?, similarity_only?}, ... ] }
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
# confidence with enough elements. Four-eyes requires a FULL, VALIDATED element
# match: every legal element is present (count == elements_total) AND the label
# is not merely a similarity signal. A similarity_only label — or any label with
# fewer than all elements — can never reach four-eyes; it is ASK at most. This is
# the Phase-A/C safety invariant: BLOCK/four-eyes only on a full element match,
# everything uncertain to ASK. ---
four_eyes_match if {
	some l in input.labels
	l.elements_total
	count(_official_met(l)) >= l.elements_total
	not l.similarity_only
}

# Fix #4: count only elements that belong to the concept's OFFICIAL element set
# (when the label carries one). A name outside the official set cannot count
# toward a full match. If official_elements is absent, fall back to elements_met.
_official_met(l) := met if {
	l.official_elements
	met := {e | some e in l.elements_met; e in l.official_elements}
} else := met if {
	met := {e | some e in l.elements_met}
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

# Phase A: a similarity_only signal (confident margin vs exemplars, but the full
# legal-element match is NOT met) routes to ASK — a human review. It can never
# reach four-eyes or deny, so it only ever adds review, never a BLOCK.
ask_match if {
	some l in input.labels
	l.similarity_only == true
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
