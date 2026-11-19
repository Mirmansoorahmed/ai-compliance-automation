# AI Compliance Automation — Makefile
# Core component: Semantic Guard (emits labels; OPA decides).
# The oss profile runs on the Python standard library alone.

PYTHON ?= python3
PROFILE ?= oss
# The oss profile runs from source with no install step; put src/ on the path.
export PYTHONPATH := src

.PHONY: help test opa-test schema eval coverage demo check-demo check-adapters-demo report all

help:
	@echo "Targets:"
	@echo "  test      Run the pytest suite"
	@echo "  schema    Validate requirement/interpretation YAML against JSON Schema"
	@echo "  opa-test  Run 'opa test' on policy/ (requires the opa binary)"
	@echo "  eval        Run the eval set (metrics persisted with timestamp + git SHA)"
	@echo "  hybrid-eval Run the hybrid eval (vendor path scored separately; see docs/HYBRID.md)"
	@echo "  coverage    Build the requirement coverage report"
	@echo "  demo      Run the 15-minute oss demo (fixture mode)"
	@echo "  check-demo          POST /v1/check — four decisions (offline)"
	@echo "  check-adapters-demo guardrails-hook — four payloads x both tools (offline)"
	@echo "  report    Build the PDF evidence pack (fails closed on missing fields)"

test:
	@$(PYTHON) -m pytest

schema:
	@$(PYTHON) -m aca.register.validate requirements interpretations

opa-test:
	@if command -v opa >/dev/null 2>&1; then \
		opa test policy -v ; \
	else \
		echo "opa binary not found — install OPA to run 'opa test'." ; \
		echo "Policy logic is also mirrored in tests/test_policy_mirror.py (pytest)." ; \
		exit 1 ; \
	fi

eval:
	@$(PYTHON) -m aca.eval.runner

hybrid-eval:
	@$(PYTHON) -m aca.eval.hybrid_runner

coverage:
	@$(PYTHON) -m aca.eval.coverage

demo:
	@$(PYTHON) -m aca.demo

check-demo:
	@$(PYTHON) -m aca.check.demo

check-adapters-demo:
	@$(PYTHON) -m guardrails_hook.demo

report:
	@$(PYTHON) -m aca.report.build
