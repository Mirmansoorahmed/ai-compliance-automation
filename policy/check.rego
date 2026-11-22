package compliance.check

# /v1/check decision over the fired catalog checks. OPA is the only decision
# point. Precedence (strictest wins): BLOCK > ASK > WARN > ALLOW.
#
# Data (generated from catalog.yaml, the single source of truth):
#   data.catalog.checks[id].dec          -> "BLOCK" | "ASK" | "WARN" | "ALLOW"
#   data.obligations.obligations[id]     -> [artefact keys]
#
# Input:
#   { "fired":   ["AIA-A3-4a", ...],   # primary checks: catalog decision drives the tier
#     "related": ["GDPR-35", ...],     # companion duties: clamped to WARN in the bundle
#     "partial_social": true|false }   # a 2-of-3 social-scoring match
#
# A partial social-scoring (AIA-5-1-c) pattern routes to ASK, never BLOCK and
# never ALLOW; the full three-element pattern is required for an automatic BLOCK
# (the full-match path lives in the Semantic Guard + compliance.tier policy).
#
# Related checks add their obligations/refs but are clamped to WARN: they are
# legal duties attached to a high-risk use case, not independent gates. GDPR-22
# escalation to ASK is decided by the caller (solely-automated effect) and
# passed in via ``fired``.
#
# This package is separate from compliance.tier (the existing deny/ask/four-eyes
# /allow label tier), which is unchanged.

import rego.v1

_rank := {"ALLOW": 0, "WARN": 1, "ASK": 2, "BLOCK": 3}

# Effective decision for a primary fired check id.
effective_decision(id) := "ASK" if {
	id == "AIA-5-1-c"
	input.partial_social == true
} else := d if {
	d := data.catalog.checks[id].dec
} else := "ALLOW"

# Clamp a related check's catalog decision to at most WARN.
clamped_decision(id) := "WARN" if {
	_rank[data.catalog.checks[id].dec] > _rank.WARN
} else := d if {
	d := data.catalog.checks[id].dec
} else := "ALLOW"

all_ranks contains r if {
	some id in input.fired
	r := _rank[effective_decision(id)]
}

all_ranks contains r if {
	some id in input.related
	r := _rank[clamped_decision(id)]
}

default decision := "ALLOW"

decision := d if {
	count(all_ranks) > 0
	best := max(all_ranks)
	some name, rank in _rank
	rank == best
	d := name
}

# Union of obligations across all fired + related checks that have any.
obligations contains o if {
	ids := array.concat(input.fired, object.get(input, "related", []))
	some id in ids
	some o in data.obligations.obligations[id]
}
