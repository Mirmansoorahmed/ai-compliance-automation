# Gap list and build plan — ai-coding-compliance-guardrails-eu (v2)

> Northwind Advisory for Halvaro Payments GmbH (fictional). Design document. Compares the current repo (formerly ai-compliance-automation, branch `spec`) with the v2 architecture. No design-decisions document yet; that comes later.

## 1. What exists today vs what v2 needs

| Area | Exists today (ACA) | Needed for v2 | Gap size |
|---|---|---|---|
| Semantic Guard | Stages 0, 1, A, S; MiniLM multilingual on CPU; labels with legal elements; DE/EN exemplars for Art. 5(1)(c), small set for 5(1)(f); `POST /v1/labels`; fail-safe to ASK | Exemplars + elements for the other Art. 5 points (a, b, ba, bb, d, e, g, h), all Annex III points, GDPR Art. 9/22 intents; better held-out recall | **Large** (data work + eval) |
| Eval | 77 tuning cases, 21 held-out; committed runs with git SHA. Tuning: precision 1.0, strict recall 0.82. Held-out: strict recall 0.11 | Per-check eval sets (attack, lawful hard negatives, ambiguous; DE + EN), held-out per concept, adapter end-to-end tests | Large |
| OPA policy | `tier.rego`: deny > four-eyes > ask > allow; thresholds; confirmed patterns; `opa test` | WARN tier, obligations per check from `catalog.yaml`, `deploy.rego`, bundle signing | Medium |
| Requirement register | 11 requirements (AI Act 5(1)(c), 5(1)(f), 9, 12, 14; ISO 27001 A.5.3, 5.14, 5.15, 5.34, 8.12, 8.15), JSON schema, coverage report | The 120-check catalog as register; coverage per law | Medium (generated) |
| `use-case.yaml` | — | Schema, Guard-proposed draft, validation | Medium |
| Policy service `/v1/check` | — (only `/v1/labels`) | One endpoint for prompt / tool / diff / deploy events | Medium |
| Guides per tool | — | Generated `CLAUDE.md`, `.cursor/rules`, `AGENTS.md`, `copilot-instructions.md`, `.kiro/steering` | Small |
| Adapters (hooks) | — | `guardrails-hook` for Claude Code, Cursor, Copilot, Codex, Kiro; MCP tool `compliance_check` | Medium |
| CI gate | CI for the repo's own tests, schema, OPA tests | Reusable `guardrails-ci` action: diff scan, Semgrep, gitleaks, dependency + IaC scan, AI-BOM, obligations comment, required check | Medium |
| Deploy gate | — | GitHub environment gate + optional protection-rule app; Gatekeeper policy; Azure Pipelines check (documented) | Medium |
| Runtime | Agent Trust Gateway exists (separate repo, unchanged) | Link and integration test only; app-side disclosure / region helpers | Small |
| Evidence | OTel decision spans with redaction; evidence-pack PDF that fails closed | Spans from every enforcement point; mapping to ISO 42001 + AI Act; ChatGPT/Codex compliance-log import (optional) | Medium |
| Human review | Four-eyes recorder writes interpretation + eval cases via PR; CODEOWNERS | Artefact approvals (two distinct people), break-glass record, concern channel | Small–medium |
| Hybrid / Azure | Prompt Shields, judge and Entra adapters (off by default); one real hybrid run done, resource group deleted | Optional Container Apps demo in Germany West Central | Small, only with Mir's go |
| Docs | README, DESIGN, AGENT-SECURITY-FRAMEWORK, FOUR-EYES, HYBRID | v2 README + rename, catalog, architecture, diagrams (this folder) | Small |

## 2. Build plan (each phase ends with a demo)

| Phase | Build | Demo at the end | Depends on |
|---|---|---|---|
| **0. Rename and scope** | Mir renames the repo on GitHub to `ai-coding-compliance-guardrails-eu`. Kiro adds the v2 docs from this folder, `catalog.yaml` as policy data, new README scope. | Repo page tells the new story; catalog renders; `opa test` still green | Mir: rename + merge PR #1 |
| **1. One API, four decisions** | `use-case.yaml` schema; `POST /v1/check`; WARN tier + obligations in Rego (generated from the catalog); keep existing deny/ask logic | Three calls: CV screening → WARN with obligations; social scoring → BLOCK; fraud score → ALLOW | 0 |
| **2. First two adapters** | `guardrails-hook` + generated guides for **Kiro** and **Claude Code** (the tools Mir uses) | Live in the IDE: CV prompt shows WARN and obligations; social-scoring prompt is refused; a secret write is denied | 1 |
| **3. CI gate** | `guardrails-ci` action: diff scan, gitleaks, Semgrep, schema, artefact check, PR comment, AI-BOM; branch ruleset makes it required | PR with a secret fails; PR with the CV feature passes with a 6-item pending checklist | 1 |
| **4. Deploy gate** | `deploy.rego`; GitHub `production` environment with a gate job and required reviewers; Gatekeeper policy on a local kind cluster | First deploy blocked ("DPIA, oversight plan missing"); after two approvals it deploys; same deny shown by Gatekeeper | 3 |
| **5. Wider detection** | Exemplars and legal elements for the remaining Art. 5 points and the Annex III areas most relevant to a fintech (4a, 4b, 5b, 5c, 1c), GDPR Art. 9/22 intents; new held-out sets; re-run eval on the box with the real model | New eval table, tuning and held-out reported separately, honest about misses | 1 |
| **6. Remaining adapters + runtime link** | Cursor, Copilot, Codex adapters; MCP tool `compliance_check`; integration test against the unchanged Agent Trust Gateway | Same CV / social-scoring / secret scenario in a second tool; one gateway-blocked tool call in the trace | 2 |
| **7. Evidence pack v2** | Spans from all points, ISO 42001 / AI Act mapping table, approvals and break-glass records in the PDF | Auditor view: one use case from prompt to production with every decision and signature | 4 |
| **8. Deployable package** | docker-compose stack; policy-service image + signed OPA bundle on GHCR; optional Azure Container Apps run in Germany West Central (budget alert first, delete after) | `docker compose up` on a clean machine runs the full story; cloud run only after Mir's explicit OK | 4, 7 |

Order rationale: phases 1–4 give a complete, honest end-to-end story with the existing detector. Phase 5 then improves the weakest part (held-out recall) with real eval runs.

## 3. Not in scope now

- Design-decisions document (later, in Mir's own words).
- Changes to the Agent Trust Gateway repo.
- Any claim of legal conformity or certification.
- Paid cloud resources without Mir's explicit approval.
