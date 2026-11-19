package compliance.deploy

# Deploy gate. A high-risk feature may reach production only when every required
# obligation artefact is recorded in use-case.yaml AND approved by two distinct
# people (four-eyes). Otherwise the deploy is DENIED, naming what is missing.
#
# This is separate from compliance.check (the /v1/check tier) and
# compliance.tier (the label tier); both are unchanged.
#
# Input:
#   { "obligations": ["dpia", "oversight_plan", ...],
#     "artefacts":   {"dpia": "docs/dpia.md", "oversight_plan": null, ...},
#     "approvals":   [ {"artefact": "dpia", "approver": "alice"}, ... ]
#                    | ["alice", "bob"],
#     "break_glass": {"active": true, "justification": "...", "approver": "..."} }
#
# Python mirror: src/aca/check/deploy.py (kept in lockstep; tests check both).

import rego.v1

required_approvers := 2

# An artefact is present when its path is a non-empty string.
present(key) if {
	p := input.artefacts[key]
	is_string(p)
	trim_space(p) != ""
}

# Distinct approver identities covering artefact `key`.
approvers(key) := s if {
	names := {who |
		some item in input.approvals
		who := approver_name(item, key)
	}
	s := names
}

# Record form: {"artefact": key|"*"|"all", "approver": who}.
approver_name(item, key) := who if {
	is_object(item)
	art := object.get(item, "artefact", object.get(item, "obligation", "*"))
	art in {key, "*", "all"}
	who := object.get(item, "approver", object.get(item, "by", object.get(item, "name", "")))
	who != ""
}

# Flat form: a bare approver name applies to every artefact.
approver_name(item, _) := item if {
	is_string(item)
}

# Break-glass: active + justified + named approver -> allowed (audited).
break_glass_ok if {
	input.break_glass.active == true
	trim_space(object.get(input.break_glass, "justification", "")) != ""
	trim_space(object.get(input.break_glass, "approver", "")) != ""
}

# Deny reasons.
missing_artefacts contains key if {
	some key in input.obligations
	not present(key)
}

under_approved contains key if {
	some key in input.obligations
	present(key)
	count(approvers(key)) < required_approvers
}

deny contains msg if {
	not break_glass_ok
	some key in missing_artefacts
	msg := sprintf("%s artefact missing", [key])
}

deny contains msg if {
	not break_glass_ok
	some key in under_approved
	msg := sprintf("%s has %d approver(s); %d distinct required", [key, count(approvers(key)), required_approvers])
}

default allow := false

allow if break_glass_ok

allow if {
	not break_glass_ok
	count(deny) == 0
}

decision := "ALLOW" if allow

decision := "DENY" if not allow
