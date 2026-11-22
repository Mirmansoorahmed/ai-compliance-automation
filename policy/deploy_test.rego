package compliance.deploy_test

import data.compliance.deploy
import rego.v1

# The CV-screening obligations (Annex III 4(a)) used across these cases.
_obligations := ["risk_management", "dpia", "oversight_plan", "eval_report", "worker_information"]

_all_present := {
	"risk_management": "docs/rm.md",
	"dpia": "docs/dpia.md",
	"oversight_plan": "docs/oversight.md",
	"eval_report": "docs/eval.md",
	"worker_information": "docs/worker-info.md",
}

_two_each := [
	{"artefact": "*", "approver": "alice"},
	{"artefact": "*", "approver": "bob"},
]

test_denied_when_artefacts_missing if {
	deploy.decision == "DENY" with input as {
		"obligations": _obligations,
		"artefacts": {"dpia": null, "oversight_plan": null},
		"approvals": [],
	}
}

test_deny_names_dpia_and_oversight if {
	denies := deploy.deny with input as {
		"obligations": ["dpia", "oversight_plan"],
		"artefacts": {"dpia": null, "oversight_plan": null},
		"approvals": [],
	}
	denies == {"dpia artefact missing", "oversight_plan artefact missing"}
}

test_denied_when_only_one_approver if {
	deploy.decision == "DENY" with input as {
		"obligations": ["dpia"],
		"artefacts": {"dpia": "docs/dpia.md"},
		"approvals": [{"artefact": "dpia", "approver": "alice"}],
	}
}

test_same_person_twice_is_one_approver if {
	deploy.decision == "DENY" with input as {
		"obligations": ["dpia"],
		"artefacts": {"dpia": "docs/dpia.md"},
		"approvals": [
			{"artefact": "dpia", "approver": "alice"},
			{"artefact": "dpia", "approver": "alice"},
		],
	}
}

test_allowed_when_present_and_two_distinct_approvers if {
	deploy.decision == "ALLOW" with input as {
		"obligations": _obligations,
		"artefacts": _all_present,
		"approvals": _two_each,
	}
}

test_break_glass_allows_with_justification if {
	deploy.decision == "ALLOW" with input as {
		"obligations": _obligations,
		"artefacts": {"dpia": null},
		"approvals": [],
		"break_glass": {"active": true, "justification": "incident INC-42 hotfix", "approver": "ciso"},
	}
}

test_break_glass_without_justification_still_denies if {
	deploy.decision == "DENY" with input as {
		"obligations": ["dpia"],
		"artefacts": {"dpia": null},
		"approvals": [],
		"break_glass": {"active": true, "justification": "", "approver": "ciso"},
	}
}

test_no_obligations_allows if {
	deploy.decision == "ALLOW" with input as {
		"obligations": [],
		"artefacts": {},
		"approvals": [],
	}
}
