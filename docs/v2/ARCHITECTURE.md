# Architecture v2 — ai-coding-compliance-guardrails-eu

> Northwind Advisory for Halvaro Payments GmbH (fictional client, Berlin fintech). Design document; nothing here is built yet unless marked **exists**. Synthetic data only. Not legal advice and not a conformity claim. Formerly *ai-compliance-automation* (ACA); the existing Semantic Guard, OPA tiers, four-eyes loop and evidence spans are reused.

Companion files in this folder:
- [`COMPLIANCE-CATALOG.md`](COMPLIANCE-CATALOG.md) — 120 checks (EU AI Act, GDPR, German add-ons, ISO/IEC 42001, security, DORA) and [`../../policy/catalog/catalog.yaml`](../../policy/catalog/catalog.yaml), the same catalog in machine-readable form (the single source of truth for policy data).
- [`GAP-AND-BUILD-PLAN.md`](GAP-AND-BUILD-PLAN.md) — what ACA has today, what must be built, in demoable phases.
- [`img/architecture-v2.png`](img/architecture-v2.png) and [`img/request-flow-v2.png`](img/request-flow-v2.png).

---

## 1. The simple story

Halvaro's developers write code with AI tools: Claude Code, Cursor, GitHub Copilot, Codex and Kiro. The firm wants three things. Nobody should be able to build something the EU AI Act forbids. High-risk features should be allowed, but must not reach production without the paperwork and the human controls the law requires. Ordinary security mistakes, such as a secret in the code, should be caught before they ship.

The harness checks the same rules at four points: when the developer types the request, when the agent writes a file or calls a tool, when the pull request is opened, and when someone tries to deploy. One policy bundle holds the rules, so all four points always agree.

**Story A: Lena builds a CV screening tool.** Lena types into Claude Code: *"Build a CV screening tool that scores applicants and shortlists the top 20."*
1. Before the model sees the prompt, a small hook script sends it to the policy service.
2. The Semantic Guard recognises the meaning (recruitment, ranking people), not just keywords. OPA matches check **AIA-A3-4a**: EU AI Act Annex III point 4(a), high-risk.
3. The decision is **WARN**. Lena may keep working, and the agent tells her what is now required: a risk assessment, a DPIA, a human-oversight plan, an evaluation report, worker information and a GDPR Art. 22 check. The agent also drafts a `use-case.yaml` that declares the purpose.
4. Lena opens a pull request. The CI gate scans the diff and finds no prohibited pattern and no secret. It posts a checklist of the six open artefacts. The code may merge, but its status stays *pending*.
5. Lena tries to deploy. The **deploy gate** asks OPA whether every required artefact exists and was approved by two different people. They do not, so the deployment is **blocked**, with a list of what is missing.
6. The DPO signs the DPIA and the HR-tech owner signs the oversight plan. The gate asks again and gets **ALLOW**. The deployment runs, and the evidence pack is updated for the auditor.

**Story B: someone asks for social scoring.** *"Join badge logs, Slack activity and canteen data per employee into a reliability index and cut the bottom 10% from the bonus pool."* The prompt never mentions "social scoring". The Guard finds all three legal elements of Art. 5(1)(c): behaviour joined across sources, an aggregated score, and detrimental treatment. OPA returns **BLOCK**, and the agent refuses and names the rule. If only two of the three elements match, the case goes to a human (ASK) instead of being allowed.

**Story C: a secret in the code.** *"Here is the Azure key, put it in config.py."* The file-write hook runs a deterministic secret scan and **blocks** the write. If the developer commits the key by hand, the required CI check (gitleaks) fails and the merge is blocked.

The same three stories appear in [`img/request-flow-v2.png`](img/request-flow-v2.png).

---

## 2. Layered architecture

![Architecture v2](img/architecture-v2.png)

| # | Layer | What it does | Runs where | Status |
|---|---|---|---|---|
| 1 | **Guides** (feed-forward) | Rules the agent reads before it works: do-not-build list, high-risk list, how to write `use-case.yaml`. Generated from the catalog, one file per tool. | In the repo, plus centrally managed copies | New |
| 2 | **Adapters** (hooks) | Thin scripts that catch a prompt or a tool call, send a normalised event to the policy service, and reply in the tool's own format. | Developer machine / cloud agent | New |
| 3a | **Policy service** `POST /v1/check` | One API for all events (prompt, tool call, diff, deploy). Calls the Guard, reads `use-case.yaml`, asks OPA, returns the decision and obligations. | Container | New (wraps the existing `POST /v1/labels`) |
| 3b | **Semantic Guard** | Emits labels: concept, legal elements met, confidence. Never decides. | Same container | **Exists** (ACA): Art. 5(1)(c) full, 5(1)(f) partial |
| 3c | **`use-case.yaml`** | The repo's declaration of intended purpose, Annex III area, role, data, owner and artefact links. | In each product repo | New |
| 3d | **OPA policy bundle** | Rego + catalog data. Strictest outcome wins: deny > ask > warn > allow. Signed; changed only via a four-eyes PR. | OPA sidecar / CI runner / gate | **Exists** in part (deny/four-eyes/ask/allow tiers); WARN + obligations new |
| 4 | **CI gate** | Required pull-request check: Guard scan of the diff, Semgrep, gitleaks, dependency scan, schema and artefact check, AI-BOM, a PR comment with obligations. | GitHub Actions | New (ACA has CI for its own tests) |
| 5 | **Deploy gate** | Blocks deployment when prohibited code is present, or a high-risk use case lacks approved artefacts. | GitHub environment / Kubernetes admission / Azure Pipelines | New |
| 6 | **Runtime** | Agent Trust Gateway: per-call OPA, tool-list pinning, token exchange. App checks: AI disclosure, EU region, stop button. | Production | Gateway **exists** (separate repo, linked, unchanged) |
| 7 | **Evidence store** | Every decision span, artefact and approval, mapped to ISO/IEC 42001 and AI Act Art. 12 / 26(6). Produces the evidence pack. | Append-only storage | **Exists** in part (OTel decision spans, evidence-pack PDF) |
| 8 | **Human review** | Four-eyes on ASK cases and policy changes; break-glass for emergencies. | GitHub PR + CODEOWNERS | **Exists** in part (four-eyes interpretation PR) |

### 2.1 Decision model

| Decision | IDE / agent | CI | Deploy gate |
|---|---|---|---|
| **BLOCK** | Prompt refused or tool call denied, with the rule and a link | Check fails | Denied |
| **ASK** | Agent pauses; a reviewer is asked (in the cloud Copilot agent, "ask" counts as deny because nobody is there to answer) | Check fails until an interpretation is merged | Denied until approved |
| **WARN** | Continues; obligations shown and written to `use-case.yaml` | Passes with a *pending* status and checklist | **Denied until artefacts exist and are approved** |
| **ALLOW** | Nothing visible; logged | Passes | Allowed |

**Fail-safe (exists in ACA):** if the Guard is down or slow, deterministic checks still run and risky actions degrade to ASK, never to a silent allow. Prompt-hook timeouts in Claude Code block the prompt by design, which matches this rule.

### 2.2 Core contracts

**`use-case.yaml`** (one per AI feature, in the product repo):

```yaml
id: uc-hr-cv-screening
title: CV pre-screening for apprenticeships
intended_purpose: rank applications and propose a shortlist for a human recruiter
ai_system: true
role: deployer            # provider | deployer | both
annex_iii: ["4(a)"]       # or [] ; proposed by the Guard, confirmed by a human
art6_3_exception: false   # if true -> art6-3-assessment required, profiling must be false
profiling: true
personal_data: [cv, contact, education]
special_categories: []
countries_of_processing: [DE]
owner: hr-tech-lead
human_overseer: recruiting-team-lead
artefacts:                # paths; the deploy gate checks presence + approvals
  risk_management: compliance/risk.md
  dpia: compliance/dpia.md
  fria: null              # required only for Annex III 5(b)/5(c) or public services
  oversight_plan: compliance/oversight.md
  eval_report: compliance/eval.json
  worker_information: compliance/works-council.md
approvals: []             # filled by the review workflow, never by hand
```

**`POST /v1/check`** request and response (normalised across all tools):

```json
{ "event": "prompt | tool | diff | deploy",
  "tool": "claude-code | cursor | copilot | codex | kiro | mcp | ci | gate",
  "repo": "halvaro/hr-portal", "actor": "pseudonym-7f3a",
  "text": "Build a CV screening tool ...",            "tool_call": null,
  "diff_ref": null, "use_case": "uc-hr-cv-screening" }

{ "decision": "warn",
  "checks": ["AIA-A3-4a", "GDPR-22", "GDPR-35", "AIA-26-7", "DE-BETRVG-87"],
  "obligations": ["risk_management", "dpia", "oversight_plan", "eval_report", "worker_information"],
  "message": "High-risk under EU AI Act Annex III 4(a). You can continue; deployment needs these artefacts.",
  "evidence_id": "ev-2026-11-...", "labels": [ { "concept_id": "AIA-A3-4a", "confidence": 0.0, "elements_met": [] } ] }
```

(The confidence value above is a placeholder in the schema, not a measured result.)

**OPA bundle layout:**

```
policy/
  tier.rego            # exists: deny > four-eyes > ask > allow  -> add warn + obligations
  obligations.rego     # new: check_id -> required artefacts (from catalog.yaml)
  deploy.rego          # new: deploy-gate rules (section 5)
  data/
    catalog.json       # generated from catalog.yaml (120 checks)
    thresholds.json    # exists
    confirmed_prohibited_patterns.json   # exists; filled only via four-eyes PR
```

---

## 3. Adapters: how each tool plugs in

All adapters use the same small script (`guardrails-hook`). It reads the hook's JSON from stdin, maps it to the event above, calls `/v1/check`, and prints the answer in the format the tool expects. Only the last step differs per tool. The extension points below were checked against each vendor's documentation on 18 Nov 2026.

| Tool | Guides (feed-forward) | Prompt check | Tool / file check | Central enforcement | Notes |
|---|---|---|---|---|---|
| **Claude Code** | `CLAUDE.md` | `UserPromptSubmit` hook; returns `decision: "block"` with a reason, or adds context | `PreToolUse` hook with `matcher` (e.g. `Write\|Edit\|Bash\|mcp__.*`); returns `permissionDecision: allow / deny / ask` | `managed-settings.json` (MDM or server-managed); `allowManagedHooksOnly` so user hooks cannot replace ours; `allowedMcpServers` / `deniedMcpServers` | Hooks can be `command` or `http`; a prompt-hook timeout blocks the prompt (fail-closed) |
| **Cursor** | `.cursor/rules`, `AGENTS.md`, Team Rules (dashboard) | `beforeSubmitPrompt`; returns `continue: false` + `user_message` | `preToolUse`, `beforeShellExecution`, `beforeMCPExecution`, `beforeReadFile`; return `permission: allow / deny / ask` | Team hooks and enterprise-managed hooks from the dashboard | `afterFileEdit` can trigger a diff scan |
| **GitHub Copilot** | `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`, organisation instructions | `userPromptSubmitted` exists, but **output from command/http config hooks is dropped**, so it can log but cannot block | `preToolUse` in `.github/hooks/*.json`; returns `permissionDecision: allow / deny` (in the cloud agent "ask" = deny) | Hooks file must be on the default branch for the cloud agent; enterprise MCP allowlist; CI as the hard gate | Prompt-level BLOCK is therefore enforced at the first tool call and in CI |
| **Codex (ChatGPT)** | `AGENTS.md` | `UserPromptSubmit`; returns `decision: "block"` or exit code 2 | `PreToolUse`; returns `permissionDecision: "deny"` | `/etc/codex/hooks.json` (system) or hooks declared in `requirements.toml` by admins; project hooks in `.codex/hooks.json` need review and trust by hash | Compliance Logs Platform (Enterprise) exports Codex prompts and tool calls to the evidence store |
| **ChatGPT (chat, not Codex)** | Workspace custom instructions | **No documented pre-prompt hook** for third parties | Workspace app / connector controls | Compliance Logs Platform: detective only (logs exported, 30-day source retention) | Treat as detect-and-review, not prevent. Code still meets the CI and deploy gates. |
| **Kiro** | `.kiro/steering/*.md`; team steering pushed via MDM to `~/.kiro/steering` | Prompt Submit hook (shell command); non-zero exit blocks the prompt | Pre Tool Use hook; non-zero exit blocks the tool call | Global hooks in `~/.kiro/hooks/` (CLI); enterprise governance in preview | Post File Save hook can run the diff scan |
| **Generic MCP client** | n/a | n/a | The policy service is also exposed as an MCP tool `compliance_check`; the **Agent Trust Gateway** sits in front of MCP servers and asks OPA per call | Gateway allowlist + SHA-256 pinning of tool lists | Gateway repo is linked, not changed |

Example (Claude Code, managed settings excerpt):

```json
{
  "allowManagedHooksOnly": true,
  "hooks": {
    "UserPromptSubmit": [ { "hooks": [ { "type": "command", "command": "guardrails-hook claude prompt" } ] } ],
    "PreToolUse": [ { "matcher": "Write|Edit|MultiEdit|Bash|mcp__.*",
                      "hooks": [ { "type": "command", "command": "guardrails-hook claude tool" } ] } ]
  }
}
```

Example (Kiro, `.kiro/hooks/guardrails.json`, shape as in Kiro's hook docs):

```json
{ "version": "v1",
  "hooks": [ { "name": "EU AI compliance check", "trigger": "PreToolUse",
               "action": { "type": "command", "command": "guardrails-hook kiro tool" } } ] }
```

**Why guides and hooks both exist.** Guides make the agent *likely* to do the right thing (cheap, but the model can ignore them). Hooks make it *certain* at that point (deterministic decision on every prompt and tool call). CI and the deploy gate make it certain even if someone works without any AI tool or turns the hooks off.

Sources: [Claude Code hooks](https://code.claude.com/docs/en/hooks), [Claude Code settings](https://code.claude.com/docs/en/settings), [Cursor hooks](https://cursor.com/docs/agent/hooks), [Cursor rules](https://cursor.com/docs/context/rules), [Copilot hooks how-to](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/use-hooks), [Copilot hooks reference](https://docs.github.com/en/copilot/reference/hooks-configuration), [Copilot repository instructions](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions), [Codex hooks](https://developers.openai.com/codex/hooks), [Codex AGENTS.md](https://developers.openai.com/codex/guides/agents-md), [OpenAI Compliance Platform](https://help.openai.com/en/articles/9261474-openai-compliance-platform-for-enterprise-and-edu-customers), [Kiro hooks](https://kiro.dev/docs/hooks/), [Kiro hook actions](https://kiro.dev/docs/hooks/actions), [Kiro steering](https://kiro.dev/docs/steering/).

---

## 4. CI gate

A reusable GitHub Action (`guardrails-ci`) runs on every pull request and is made a **required status check** with a branch ruleset, so a red check blocks the merge.

Steps:
1. **Schema:** `use-case.yaml` exists if the diff adds an AI SDK, model file or inference call (AIA-UC-DECL), and it validates.
2. **Semantic diff scan:** the Guard's artefact stage (Stage A, exists for Art. 5(1)(c)) labels the diff; OPA decides.
3. **Deterministic scans:** gitleaks (secrets), Semgrep (unsafe use of LLM output, injection, raw SQL), dependency and licence scan, IaC scan for non-EU regions and public endpoints.
4. **AI-BOM:** CycloneDX ML-BOM listing models, datasets, MCP servers and AI services.
5. **Obligations:** compares the checks hit with the artefacts present and posts a checklist comment.
6. **Evidence:** writes a decision span with the commit SHA.

Result: BLOCK or unresolved ASK fails the check. WARN passes with a *pending obligations* status, so engineering is not stopped, but the deploy gate will be.

---

## 5. Deploy gate (block deployment)

The deploy gate is a separate control from CI because the question is different. CI asks whether the code is safe to merge. The deploy gate asks whether this use case is allowed to go live. It runs `deploy.rego` with three inputs: `use-case.yaml`, the artefact files with their approval records, and the CI result for the exact commit.

**Rules (plain words):**
- Deny if any BLOCK check fired on this commit and no approved legal exception exists.
- Deny if any ASK check is unresolved.
- If `annex_iii` is not empty: deny unless risk management, oversight plan and eval report exist and each is approved by two different people, neither of them the author.
- If personal data plus profiling or Annex III: deny unless a DPIA exists and is approved by the DPO role.
- If Annex III 5(b) or 5(c), or the deployer provides public services: deny unless a FRIA exists.
- If the system interacts with people (Art. 50(1)): deny unless the disclosure text exists in the UI resources.
- If `art6_3_exception: true` while `profiling: true`: deny (the exception cannot apply).
- Deny if the image has no signed build provenance from the gated pipeline.

**Three ways to wire it (pick per platform):**

| Platform | How it blocks | Cost note |
|---|---|---|
| **GitHub Actions** (demo default) | The deploy job uses `environment: production`. The first step runs the gate (`opa eval` on the bundle) and fails the job on deny. Optionally a **custom deployment protection rule** (a small GitHub App) receives the `deployment_protection_rule` webhook, calls the policy service, and approves or rejects through the REST API. Required reviewers add the human sign-off. | Environments and protection rules are available on public repositories on all plans; private repositories need paid plans (custom rules need Enterprise). The demo repo is public. |
| **Kubernetes / GitOps** | **OPA Gatekeeper** admission policy: a pod is admitted only if it carries a `use-case-id` label and a signed attestation whose gate decision is allow. Argo CD syncs fail if admission denies. | Runs on a local kind cluster for the demo, no cloud cost. |
| **Azure Pipelines** | Environment **Approvals and checks**: an *Invoke REST API* check calls the policy service; a manual approval adds the four-eyes step. | Only if Halvaro uses Azure DevOps. |

**Break-glass.** For an outage fix, two approvers (Security + the product owner) can record a time-boxed exception. The gate accepts it only for that commit, opens a ticket, and requires a review afterwards. A BLOCK under Art. 5 has no break-glass; only a documented legal exception (e.g. the medical or safety reason in Art. 5(1)(f)) can lift it, again with four-eyes.

Sources: [GitHub environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments), [custom deployment protection rules](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/create-custom-protection-rules), [ruleset rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets), [OPA Gatekeeper](https://open-policy-agent.github.io/gatekeeper/website/docs/), [Azure Pipelines approvals and checks](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/approvals), [SLSA](https://slsa.dev/).

---

## 6. Runtime

- **Agent Trust Gateway (linked, unchanged).** It already validates the agent's own token, pins each MCP server's tool list with SHA-256, asks OPA per tool call, holds risky calls for approval, and exchanges tokens. On its slow path it calls the Semantic Guard's label API, as designed in ACA. This covers OWASP ASI02, ASI03, ASI04 and ASI10 at runtime.
- **Application runtime checks.** These are small library calls in the product: show the Art. 50(1) disclosure, refuse non-EU model endpoints, keep the human-oversight stop path working, and emit decision logs kept for at least six months (Art. 26(6)).

---

## 7. Evidence store and mapping

Every decision (IDE, CI, gate, runtime, reviewer) emits one OpenTelemetry-shaped span with a pseudonymised actor, check IDs, decision, policy bundle version, Guard version and commit SHA. ACA already emits these spans and builds an evidence-pack PDF that fails closed on missing fields.

| Evidence | Supports |
|---|---|
| Decision spans + retention config | AI Act Art. 12, 19, 26(6); ISO 42001 A.6.2.8; ISO 27001 A.8.15 |
| `use-case.yaml` registry | ISO 42001 clause 4.3 scope / AI inventory; A.6.2.2; AI Act Art. 3(12) intended purpose |
| Risk, DPIA, FRIA, oversight plan | AI Act Art. 9, 14, 27; GDPR Art. 35; ISO 42001 6.1.2-6.1.4, A.5 |
| Eval reports with git SHA | AI Act Art. 15; ISO 42001 6.2, A.6.2.4 |
| Interpretation PRs + eval cases | ISO 42001 10.1-10.2 (corrective action); AI Act Art. 9 (iterative) |
| Approvals (four-eyes, break-glass) | ISO 42001 A.3.2; ISO 27001 A.5.3 segregation of duties |
| AI-BOM, vendor list, DPAs | ISO 42001 A.4, A.10; GDPR Art. 28; DORA Art. 28 register |
| Compliance Logs export (ChatGPT/Codex) | ISO 42001 9.1 monitoring |

Storage: an append-only evidence branch in Git for the demo; immutable (WORM) blob storage in a real deployment.

---

## 8. Human review

- **Four-eyes (exists in ACA):** ASK cases and every policy change need two distinct approvers (CODEOWNERS: Legal + Security). The reviewer's decision is written as a versioned interpretation plus new eval cases in the same PR. The system never rewrites its own policy.
- **Confirmed patterns:** only an approved interpretation can turn a pattern into an automatic deny (exists: `confirmed_prohibited_patterns`).
- **Break-glass:** see section 5.
- **Report a concern:** every BLOCK and ASK message links to a channel for raising concerns (ISO 42001 A.3.3).

---

## 9. How it is deployed

### 9.1 Local demo (zero cost)

`docker compose up` starts:

| Service | Image / content |
|---|---|
| `policy-service` | Python service: `/v1/check` + the existing Guard (`/v1/labels`), MiniLM on CPU |
| `opa` | Official OPA image, loads the bundle from `bundle-server` |
| `bundle-server` | Static file server with the signed bundle (built by `opa build`) |
| `otel-collector` + `jaeger` | Decision spans, viewable in the browser |
| `gatekeeper-demo` (optional) | kind cluster with Gatekeeper to show the admission deny |
| `agent-trust-gateway` (optional) | Pulled from its own repo, unchanged |

The adapters on the developer machine point at `http://localhost:<port>/v1/check`.

### 9.2 Deployable form

1. **Policy-service container** published to GitHub Container Registry, with signed build provenance.
2. **OPA bundle** built and signed in CI, then published as an OCI artefact (OPA can pull bundles from OCI registries) or served by any static host. Every OPA (sidecar, CI runner, Gatekeeper) loads the same bundle version, which is the single source of truth.
3. **`guardrails-ci` GitHub Action** (composite action) and a reusable **deploy-gate workflow**.
4. **Adapter pack:** `guardrails-hook` plus generated guides and hook configs per tool, distributed by managed settings or MDM (Claude Code, Kiro, Codex), the Cursor dashboard, or committed `.github/hooks` (Copilot).

### 9.3 Cloud option (minimal, only with Mir's explicit go)

- **Tier 0 (default, zero cost):** no hosted service. Hooks run `opa eval` and the Guard locally; CI and the deploy gate run inside GitHub Actions on the public demo repo.
- **Tier 1 (short demo):** one Azure Container Apps app (policy service + OPA sidecar) in **Germany West Central**, scale to zero, behind a budget alert, deleted right after the demo. No other Azure resources. Data stays in the EU.

---

## 10. Limits

- Indeterminate legal concepts are not automated. The harness flags and routes; named humans interpret.
- Semantic detection is the weakest link today: strict recall 0.82 on the 77-case tuning set, but **0.11 strict recall on the 21-case held-out set** (committed run, 18 Nov 2026, real multilingual MiniLM on CPU). Precision and benign false-block were clean (1.0 and 0.0). New Annex III and Art. 5 concepts will start with small exemplar sets, so deterministic signals, `use-case.yaml` declarations and the ASK path carry the load until held-out recall improves.
- Copilot's prompt hook cannot block, and ChatGPT chat has no pre-prompt hook; there, CI and the deploy gate are the hard controls.
- Hooks on a developer laptop can be removed by an admin user. Managed settings reduce this; the server-side CI and deploy gates are what make the control reliable.
- The vendor features listed were checked in vendor docs on 18 Nov 2026 and change often; re-check before a demo.
