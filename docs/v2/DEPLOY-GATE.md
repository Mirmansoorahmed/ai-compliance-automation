# Deploy gate — required reviewers on `production`

> The repo owner configures the GitHub environment and its reviewers by hand. Nothing here calls the GitHub API for you.

The deploy gate has two halves that must both pass before a high-risk feature reaches production:

1. **The artefact + approval check** (`compliance-gate` job in [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml)) — runs `guardrails-deploy-gate`, which resolves the feature's required obligations from the catalog and denies unless every required artefact is recorded in `use-case.yaml` **and** approved by two distinct people. This is the machine check (`policy/deploy.rego`, mirrored in `src/aca/check/deploy.py`).
2. **The GitHub `production` environment** — a protected environment with **required reviewers** (two distinct people). GitHub holds the `deploy-production` job until those reviewers approve. This is the human four-eyes step.

## Configure the `production` environment (owner, by hand)

1. Repo → **Settings** → **Environments** → **New environment** → name it `production`.
2. Enable **Required reviewers** and add **two distinct people** (or a team resolving to at least two). GitHub requires their approval before the `deploy-production` job runs.
3. Optionally add a **wait timer** and restrict deployment branches to `main`.
4. Save. The `deploy.yml` workflow's `deploy-production` job references `environment: production`, so it will now pause for review.

## How the two halves combine

- If an artefact is missing or has fewer than two approvers, `guardrails-deploy-gate` exits non-zero and the `compliance-gate` job fails, so `deploy-production` never starts.
- If the machine check passes, GitHub still holds `deploy-production` for the environment's required reviewers. Both the recorded artefact approvals (in `use-case.yaml`) and the GitHub environment approval are needed.

## Break-glass

`use-case.yaml` may carry a `break_glass` block (`active`, `justification`, `approver`). An active, justified, named override makes the machine gate ALLOW and records the override as an audited reason. It does **not** bypass the GitHub environment reviewers — the human approval still applies. Use it only for a recorded incident.

## Kubernetes (Gatekeeper)

The same rule is expressed for cluster admission under [`deploy/gatekeeper/`](../../deploy/gatekeeper/):

- `constrainttemplate.yaml` — a `ConstraintTemplate` with the deny logic (mirror of `policy/deploy.rego`).
- `constraint.yaml` — applies it to `apps/Deployment` objects that carry a `guardrails.eu/use-case` annotation.
- `tests/` — a `gator` suite with a denied case (artefacts missing) and an allowed case (present + two approvers).

Validate the policy without a cluster (to be run by the owner; `gator` ships with Gatekeeper and is not installed in this sandbox):

```bash
gator verify deploy/gatekeeper/tests/
```

Apply to a cluster (to be run by the owner, e.g. on a local `kind` cluster with Gatekeeper installed):

```bash
kubectl apply -f deploy/gatekeeper/constrainttemplate.yaml
kubectl apply -f deploy/gatekeeper/constraint.yaml
# A Deployment whose guardrails.eu/use-case annotation shows missing artefacts
# is rejected by the admission webhook with the same "artefact missing" message.
```

## Try the gate offline

```bash
make check-deploy-demo        # or: scripts/demo_deploy.sh
```

No cluster, no opa binary, no GitHub needed — it runs the Python mirror and shows the first deploy denied (DPIA + oversight plan missing), then allowed once the artefacts and two approvals are present.
