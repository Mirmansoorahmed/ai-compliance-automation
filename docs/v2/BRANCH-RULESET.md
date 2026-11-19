# Making the guardrails gate a required check on `main`

> The repo owner applies this by hand. Nothing here calls the GitHub API for you.

The Phase 3 CI gate runs as the `guardrails` job in [`.github/workflows/guardrails.yml`](../../.github/workflows/guardrails.yml). On its own, a failing gate only shows a red check — a PR can still be merged. To make it enforce, mark the check **required** on `main` with a branch ruleset.

## Option A — the GitHub UI (recommended)

1. Open the repo on GitHub → **Settings** → **Rules** → **Rulesets** → **New branch ruleset**.
2. Name it (for example `guardrails-required-on-main`) and set **Enforcement status** to **Active**.
3. Under **Target branches**, add **Include** → the default branch (`main`).
4. Enable **Require status checks to pass before merging**, then add the check named **`guardrails`**.
   - The context name is the workflow **job id**. Open any open PR's checks list to confirm the exact name GitHub shows and use that if it differs.
   - Turn on **Require branches to be up to date before merging** if you want strict checks.
5. Optionally enable **Require a pull request before merging** (one approval) and **Block force pushes**.
6. **Create** the ruleset.

From then on a PR cannot merge into `main` while the gate is failing (for example, a PR that adds a hardcoded secret → BLOCK → exit 1 → red check → merge blocked).

## Option B — import the example ruleset JSON

[`config/branch-ruleset.example.json`](../../config/branch-ruleset.example.json) is the same rule as JSON. In **Settings → Rules → Rulesets → New ruleset → Import a ruleset**, upload that file and review it before saving. Adjust the `context` value if your PR shows the check under a different name.

## Notes

- Required checks match on the **context name** reported to the commit status API, which here is the workflow job id `guardrails`. If you rename the job or add a matrix, update the ruleset to match.
- A ruleset governs merges; the gate's own exit code (BLOCK/ASK → non-zero) is what produces the failing status the ruleset keys off.
- The PR comment and the job summary are informational; the required check is the enforcement point.
