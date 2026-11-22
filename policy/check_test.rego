package compliance.check_test

import data.compliance.check
import rego.v1

# Minimal catalog + obligations stand-ins for the required Phase-1 mappings.
fixture_catalog := {"checks": {
	"AIA-5-1-c": {"dec": "BLOCK"},
	"AIA-A3-4a": {"dec": "WARN"},
	"AIA-A3-5b": {"dec": "WARN"},
	"SEC-SECRETS": {"dec": "BLOCK"},
	"GDPR-22": {"dec": "ASK"},
	"GDPR-35": {"dec": "WARN"},
	"AIA-26-7": {"dec": "WARN"},
	"DE-BETRVG-87": {"dec": "ASK"},
	"AIA-27": {"dec": "WARN"},
}}

fixture_obligations := {"obligations": {
	"AIA-A3-4a": ["risk_management", "dpia", "oversight_plan", "eval_report", "worker_information"],
	"AIA-A3-5b": ["risk_management", "dpia", "fria", "oversight_plan", "eval_report"],
}}

# Social scoring (full pattern) -> BLOCK.
test_social_scoring_blocks if {
	check.decision == "BLOCK" with input as {"fired": ["AIA-5-1-c"], "partial_social": false}
		with data.catalog as fixture_catalog
		with data.obligations as fixture_obligations
}

# Partial social scoring -> ASK, not BLOCK.
test_partial_social_asks if {
	check.decision == "ASK" with input as {"fired": ["AIA-5-1-c"], "partial_social": true}
		with data.catalog as fixture_catalog
		with data.obligations as fixture_obligations
}

# Secret in a tool/diff -> BLOCK.
test_secret_blocks if {
	check.decision == "BLOCK" with input as {"fired": ["SEC-SECRETS"], "partial_social": false}
		with data.catalog as fixture_catalog
		with data.obligations as fixture_obligations
}

# CV screening (Annex III 4(a)) with companion duties as RELATED (clamped to
# WARN) -> the bundle stays WARN even though GDPR-22/BetrVG are ASK standalone.
test_cv_screening_bundle_is_warn if {
	check.decision == "WARN" with input as {
		"fired": ["AIA-A3-4a"],
		"related": ["GDPR-22", "GDPR-35", "AIA-26-7", "DE-BETRVG-87"],
		"partial_social": false,
	}
		with data.catalog as fixture_catalog
		with data.obligations as fixture_obligations
}

# When the CV use case is solely automated, GDPR-22 comes in as a primary fired
# check (caller decision) and escalates the bundle to ASK.
test_cv_screening_solely_automated_is_ask if {
	check.decision == "ASK" with input as {
		"fired": ["AIA-A3-4a", "GDPR-22"],
		"related": ["GDPR-35", "AIA-26-7", "DE-BETRVG-87"],
		"partial_social": false,
	}
		with data.catalog as fixture_catalog
		with data.obligations as fixture_obligations
}

# Annex III 4(a) alone -> WARN.
test_annex_iii_4a_alone_is_warn if {
	check.decision == "WARN" with input as {"fired": ["AIA-A3-4a"], "related": [], "partial_social": false}
		with data.catalog as fixture_catalog
		with data.obligations as fixture_obligations
}

# Credit scoring (Annex III 5(b)) obligations include FRIA.
test_credit_scoring_obligations_include_fria if {
	obl := check.obligations with input as {"fired": ["AIA-A3-5b"], "related": [], "partial_social": false}
		with data.catalog as fixture_catalog
		with data.obligations as fixture_obligations
	"fria" in obl
}

# Nothing fired -> ALLOW (fraud score with no catalog hit).
test_no_checks_allows if {
	check.decision == "ALLOW" with input as {"fired": [], "related": [], "partial_social": false}
		with data.catalog as fixture_catalog
		with data.obligations as fixture_obligations
}
