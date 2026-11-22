# Phase 4 — the deploy gate

> Northwind Advisory for Halvaro Payments GmbH (fictional). The CI gate (Phase 3) warns and lists obligations; the deploy gate makes those obligations binding before a high-risk feature reaches production. Synthetic data only; not legal advice, not a conformity claim.

## What Phase 4 adds

- **`policy/deploy.rego`** (package `compliance.deploy`) — denies a deploy unless every required obligation artefact is recorded in `use-case.yaml` and approved by two distinct people (four-eyes), with a break-glass path. Mirrored line-for-line in **`src/aca/check/deploy.py`** so the service, tests and the offline demo run without an `opa` binary. `policy/deploy_test.rego` and `tests/test_deploy_gate.py` check the same cases. The existing `compliance.check` and `compliance.tier` packages are unchanged.
- **`guardrails-deploy-gate`** — a CLI that reads `use-case.yaml`, resolves the feature's obligations from the catalog (same engine as `/v1/check`), and applies the gate. Exit 0 = ALLOW, exit 1 = DENY.
- **`.github/workflows/deploy.yml`** — a `compliance-gate` job that runs the CLI, then a `deploy-production` job bound to a protected `production` environment. The gate must pass before the environment job runs; the environment's **required reviewers** (two distinct people) are the human half, configured by the owner — see [`DEPLOY-GATE.md`](DEPLOY-GATE.md).
- **`deploy/gatekeeper/`** — a Gatekeeper `ConstraintTemplate` + `Constraint` expressing the same rule for Kubernetes admission, with a `gator` test suite (denied / allowed cases).

## How a deploy is decided

A deploy is **ALLOWED** only when, for the feature's required obligations:

1. every required artefact has a non-empty path in `use-case.yaml`, and
2. every required artefact is approved by two distinct people, and
3. any break-glass override in force carries a justification and a named approver.

Otherwise it is **DENIED**, and the reasons name exactly what is missing (e.g. `dpia artefact missing`, `oversight_plan has 1 approver(s); 2 distinct required`). The obligation list comes from the catalog for the declared Annex III area — nothing is hardcoded.

## Run it

```bash
make check-deploy-demo        # or: scripts/demo_deploy.sh
```

Offline output:

```
Deploy gate — uc-hr-cv-screening (offline)

Required obligations (5): risk_management, dpia, oversight_plan, eval_report, worker_information

1. First deploy (no artefacts, no approvals)
   decision        : DENY
   reason          : risk_management artefact missing
   reason          : dpia artefact missing
   reason          : oversight_plan artefact missing
   reason          : eval_report artefact missing
   reason          : worker_information artefact missing

2. After artefacts recorded and approved by two distinct people
   decision        : ALLOW
   reason          : all required artefacts present and approved by two distinct people
```

This is the Phase 4 target behaviour: the first deploy is blocked because the DPIA and oversight plan (and the rest) are missing; once the artefacts are recorded and two distinct people have approved, the deploy is allowed.

## To be run by the owner

- **GitHub `production` environment + required reviewers** — configure by hand (Settings → Environments). See `DEPLOY-GATE.md`.
- **`gator verify deploy/gatekeeper/tests/`** — validates the Gatekeeper policy; `gator` is not installed in this sandbox.
- **kind cluster demo** — `kubectl apply` the template + constraint on a local cluster with Gatekeeper and watch a non-compliant Deployment be rejected. Requires Docker/kind, which this sandbox does not have.
- **`opa test policy`** — runs `policy/deploy_test.rego` (and the others); needs the `opa` binary, absent here. The Python mirror (`tests/test_deploy_gate.py`) covers the same cases in pytest.

## Limits

- The machine gate trusts `use-case.yaml`: it checks that an artefact path is recorded and that two distinct names approved it. It does not open the artefact file or verify its contents — the recorded approval is the evidence.
- The GitHub environment reviewers and the recorded `use-case.yaml` approvals are complementary; the workflow needs both.
- Break-glass allows the machine gate but never bypasses the GitHub environment reviewers.

## Scope note

Phase 4 completes the enforcement chain: editor (Phase 2) → pull request (Phase 3) → deploy (Phase 4), all on the single `/v1/check` + catalog contract. The evidence pack (Phase 7) collects the decision records from each of these points.
