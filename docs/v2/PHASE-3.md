# Phase 3 — the CI gate

> Northwind Advisory for Halvaro Payments GmbH (fictional). This explains, in plain language, the Phase 3 build: a pull-request check that runs the same compliance decision on a diff that the editor hook runs on a prompt. Synthetic data only; not legal advice, not a conformity claim.

## What Phase 3 adds

Phase 1 built the decision endpoint; Phase 2 put it in the editor. Phase 3 puts it on the pull request:

- **`guardrails-ci`** — a dependency-free CLI (standard library on the oss profile) that reads a PR diff, runs the local secret scan on the added lines, calls the **same `/v1/check` decision engine in-process** (no running service), checks the required artefacts for a high-risk use case against `use-case.yaml`, and writes a PR-comment-ready report plus an AI-BOM. Its **exit code is the gate**.
- A **composite GitHub Action** (`.github/actions/guardrails-ci`) that runs the CLI, appends the report to the job summary, uploads the report and AI-BOM as artifacts, and (optionally) posts or updates one PR comment.
- A **workflow** (`.github/workflows/guardrails.yml`) that runs the action on every pull request. The repo's existing `ci.yml` (tests, schema, OPA) is unchanged.
- **Branch-ruleset docs + example config** to make `guardrails` a required check on `main`.

The target behaviour: a PR that adds a hardcoded test credential **fails** the check; a PR that adds the CV screening feature **passes** but shows a pending-obligations checklist.

## What it checks

1. **Diff.** It reads the changed files and the added lines from `git diff base...head` (default `origin/main...HEAD`) or from `--diff-file` for fixtures. Deleted files and removed lines are ignored — the gate reasons about what the PR introduces.
2. **Secret scan.** The built-in scanner (reused from the editor hook, `guardrails_hook.secrets`) runs on the added lines. A hit is `SEC-SECRETS` → BLOCK. This runs offline and is the authoritative secret signal.
3. **Optional external scanners.** `gitleaks` and `Semgrep` run **if they are on PATH**; otherwise they are reported as *skipped (not installed)* and never fail the gate. A missing tool is not a compliance finding.
4. **Decision engine.** The added lines are sent as a `diff` event to the same `CheckService` the API builds (Semantic Guard with the offline hashed-fallback embedder + the catalog policy). The repo's `.guardrails/use-case.yaml` is passed inline, so a declared Annex III area pulls in its obligations.
5. **Artefact check.** For a WARN use case, the report lists the required artefacts from `catalog.yaml` and marks each **present** or **missing** based on the paths recorded under `artefacts:` in `use-case.yaml`. The count is whatever the catalog yields for the declared area — nothing is hardcoded.

### Exit codes (the gate)

| Decision | Exit | Effect |
|---|---|---|
| **BLOCK** | 1 | check fails |
| **ASK** | 1 (or 0 with `--ask-passes`) | check fails unless ASK is allowed to pass |
| **WARN** | 0 | check passes; obligations shown as a pending checklist |
| **ALLOW** | 0 | check passes |

## Outputs

- **`ci-report.md`** — PR-comment-ready: the decision and what it means, the rules that fired with their legal source, the pending-obligations checklist, the scanner status, and the changed files.
- **`ai-bom.json`** — a minimal CycloneDX 1.5 inventory of the AI/ML components the repo declares: the embedding model, the deterministic fallback embedder, and the declared Python dependencies. Each component carries a `guardrails:provenance` property marking the value as `declared` or `declared-in-docs` (guessed-from-docs), so a reader never mistakes an inference for a fact. It is a software inventory, not a conformity claim or a full SBOM.

## Run it

```bash
make check-ci-demo        # or: scripts/demo_ci.sh
```

Offline output:

```
1. Hardcoded test credential (secret.diff)
   decision  : BLOCK
   exit code : 1
   rules     : SEC-SECRETS

2. CV screening feature (cv-feature.diff)
   decision  : WARN
   exit code : 0
   rules     : AIA-A3-4a, GDPR-22, GDPR-35, AIA-26-7, DE-BETRVG-87
   obligations (pending checklist):
      [ ] risk_management (missing)
      [ ] dpia (missing)
      [ ] oversight_plan (missing)
      [ ] eval_report (missing)
      [ ] worker_information (missing)
```

Run the gate directly on a diff:

```bash
guardrails-ci --diff-file path/to.diff --use-case .guardrails/use-case.yaml
# or on a branch:  guardrails-ci --base origin/main --head HEAD
```

## Make it a required check

`guardrails.yml` runs the gate on every PR, but a failing check only blocks a merge once `guardrails` is marked **required** on `main`. The repo owner applies this by hand — see [`BRANCH-RULESET.md`](BRANCH-RULESET.md) and the example [`config/branch-ruleset.example.json`](../../config/branch-ruleset.example.json). This repo never calls the GitHub API to configure it for you.

## Limits

- **The gate reasons about added lines, not full program behaviour.** It is deterministic diff + catalog analysis, not a code auditor; the Semantic Guard covers the Art. 5(1)(c) social-scoring intent it was trained for, and the secret scan covers common key formats. Wider detection is Phase 5.
- **gitleaks and Semgrep are optional.** When absent the report says *skipped*; the gate decision is identical whether or not they are installed, because the built-in scan and the decision engine produce the verdict.
- **The AI-BOM is minimal.** It lists what the repo declares (pyproject + the documented model), not a resolved dependency tree. Fields that come from docs rather than a lockfile are marked `declared-in-docs`.
- **The artefact checklist trusts `use-case.yaml`.** It marks an artefact *present* when a path is recorded; it does not open the file or verify its contents or approvals — that is the deploy gate's job (Phase 4).
- **Offline by design.** The gate runs on the hashed-fallback embedder so CI is reproducible with no model download; with the real MiniLM model installed the same diff runs through the trained Guard.

## Scope note

Phase 3 enforces the decisions at pull-request time. The deploy gate (Phase 4) enforces the same obligations at release, when it checks that the artefacts the checklist listed exist and have two approvals. All phases use the single `/v1/check` contract from Phase 1.
