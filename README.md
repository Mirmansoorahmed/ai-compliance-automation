# AI Semantic Guardrails EU

**Core component: Semantic Guard** — it emits contextual intent *labels* and confidence for prompts, tool calls, and code artefacts. **OPA decides** `BLOCK` / `ASK` / `WARN` / `ALLOW`. A GitHub-native harness that catches EU-regulated AI uses at the point a developer builds them with an AI coding tool (Claude Code, Cursor, GitHub Copilot, Codex, Kiro).

> Lab / portfolio project (`ai-semantic-guardrails-eu`). **Synthetic data only** (fictional consultancy *Northwind Advisory*, fictional client *Halvaro Payments GmbH*). Mappings to the EU AI Act, GDPR, ISO/IEC 42001 and security best practice are **illustrative** and in our own words — not legal advice, not a conformity claim. Formerly *AI Compliance Automation* / *AI Coding Compliance Guardrails*; the Semantic Guard, OPA tiers, four-eyes loop and evidence spans are reused.

## The story in one paragraph

A developer asks an AI coding tool to build something. **Prohibited uses are refused at the prompt** — a request that amounts to social scoring under EU AI Act Art. 5 is blocked before the model acts on it, even when it never says "social scoring". **High-risk uses are allowed but warned and gated at deploy** — a CV-screening or credit-scoring feature (EU AI Act Annex III) keeps building, but the harness lists the artefacts the law requires (risk assessment, DPIA, human-oversight plan, evaluation report, worker information) and the deploy gate blocks production until they exist and two different people have approved them. **Ordinary security mistakes are blocked** — a secret pasted into code is caught by a deterministic scanner at the agent and again in CI. One policy bundle holds the rules, so the prompt, the tool call, the pull request and the deploy gate all agree.

## Architecture

![Architecture v2 — the policy core, adapters, CI and deploy gates, runtime and evidence](docs/v2/img/architecture-v2.png)

Full v2 design: [`docs/v2/ARCHITECTURE.md`](docs/v2/ARCHITECTURE.md) · the 120-check catalog: [`docs/v2/COMPLIANCE-CATALOG.md`](docs/v2/COMPLIANCE-CATALOG.md) and the machine-readable [`policy/catalog/catalog.yaml`](policy/catalog/catalog.yaml) · the gap list and phased plan: [`docs/v2/GAP-AND-BUILD-PLAN.md`](docs/v2/GAP-AND-BUILD-PLAN.md).

The existing Agent Trust Gateway stays the runtime PEP (separate repo, unchanged). On the slow path it calls the **Semantic Guard**. The Guard labels the request (stages 0–1 local; 2–3 optional cloud). OPA maps labels + the catalog + `use-case.yaml` to a tier. Ambiguous cases go to four-eyes review, which records an interpretation + eval cases through a PR. One OpenTelemetry-shaped span per decision carries pseudonymised evidence.

## Status (built vs planned, per phase)

| Phase | Scope | Status |
|---|---|---|
| **0 — Docs + catalog** | v2 docs under `docs/v2/`, 120-check `catalog.yaml` as policy data with JSON schema + validation test, this README | **Built** |
| **1 — One API, four decisions** | `use-case.yaml` schema + validator; `POST /v1/check` (prompt/tool/diff/deploy); Rego WARN tier + obligations from the catalog; `/v1/labels` kept; fail-safe to ASK | **Built** |
| **2 — First adapters (Kiro, Claude Code)** | `guardrails-hook` (prompt + tool-call hook → `POST /v1/check`, fail-safe to ASK, offline secret block) with Claude Code + Kiro hook configs, and tool guides generated from the catalog | **Built** |
| **3 — CI gate** | `guardrails-ci` CLI + composite action: PR-diff secret scan, same `/v1/check` engine in-process, artefact checklist, `ci-report.md` + AI-BOM, optional gitleaks/Semgrep (skipped when absent); branch-ruleset docs to make it a required check | **Built** |
| **4 — Deploy gate** | `policy/deploy.rego` (+ Python mirror): obligations must be present and approved by two distinct people; `guardrails-deploy-gate` CLI; `deploy.yml` with a gate job before a protected `production` environment; Gatekeeper ConstraintTemplate + Constraint with a `gator` suite | **Built** |
| **5 — Wider detection** | exemplars + legal elements (DE/EN) for the remaining Art. 5 points, Annex III 4a/4b/5b/5c/1c and GDPR Art. 9/22; a held-out set kept separate from tuning; offline per-concept smoke check (real recall measured by the owner with MiniLM) | **Built** |
| **5b — Vague-law classifier** | pluggable `DecisionBackend` (local open-source MiniLM, deterministic fake for tests, optional closed Jev off by default); question sets from the catalog; ACT/NO/ASK routing; eval harness (accuracy/ECE/ASK-rate to be measured) | **Built** |
| **6 — Remaining adapters + runtime link** | Cursor adapter (same hook core) + generated Copilot/Codex instructions (guidance-only, limits stated); `guardrails-mcp` server with a `compliance_check` tool; integration test against the unchanged Agent Trust Gateway contract | **Built** |
| **7 — Evidence pack v2** | spans from all points; ISO 42001 / AI Act mapping; approvals | Planned |
| **8 — Deployable package** | docker-compose; signed OPA bundle on GHCR; optional cloud demo | Planned |

Plain-language explanations: Phase 1 API and decisions — [`docs/v2/PHASE-1.md`](docs/v2/PHASE-1.md); Phase 2 adapters (Claude Code + Kiro) — [`docs/v2/PHASE-2.md`](docs/v2/PHASE-2.md); Phase 3 CI gate — [`docs/v2/PHASE-3.md`](docs/v2/PHASE-3.md); Phase 4 deploy gate — [`docs/v2/PHASE-4.md`](docs/v2/PHASE-4.md); Phase 5 wider detection — [`docs/v2/PHASE-5.md`](docs/v2/PHASE-5.md); Phase 5b vague-law classifier — [`docs/v2/PHASE-5b.md`](docs/v2/PHASE-5b.md); Phase 6 remaining adapters + runtime link — [`docs/v2/PHASE-6.md`](docs/v2/PHASE-6.md).

## Semantic Guard (core)

- **Labels, not verdicts.** `{concept_id, pattern_id?, elements_met[], confidence, evidence_refs[], detector_versions{}}`. OPA is the only decision point.
- **Rubric + exemplars, not keywords.** Detection scores against legal-element rubrics and curated DE/EN exemplars (positives and hard negatives), so "compute a fraud risk score" (lawful) stays low while a keyword-free joined-behaviour ranking with an adverse action scores high.
- **Stages:** 0 deterministic signals · 1 local embedding similarity · A artefact/diff analysis · S session context (labels only). Stages 2 (Prompt Shields) and 3 (LLM judge) are optional hybrid adapters, off by default.
- **Fail-safe.** If the Guard is down or errors, risky actions degrade to `ASK` — never a silent allow.

## How to run

The default `oss` profile runs fully offline on the Python standard library — no cloud account, no third-party install needed.

```bash
make demo      # the 3 Semantic-Guard scenarios (oss profile, offline)
make report    # build the evidence-pack PDF (fails closed on missing fields)
make test      # pytest suite
make schema    # validate the requirement/interpretation register
make opa-test  # run `opa test` on the Rego (needs the opa binary)
make eval      # run the eval set; writes a provenanced results file
make coverage  # requirement coverage report
```

The Phase 1 API can be exercised with `scripts/demo_v1_check.sh` (four `POST /v1/check` calls: CV screening → WARN, social scoring → BLOCK, fraud score → ALLOW, secret diff → BLOCK).

## Results

Metrics come only from a committed eval run (timestamp + git SHA). Where no run exists, a cell reads `TO BE MEASURED`. The tuning set is **77 synthetic cases** (DE + EN): Art. 5(1)(c) attack (incl. keyword-free and multi-turn "salami"), lawful hard negatives (fraud/credit/HR analytics), ambiguous, plus a separate **PROMPT-INJECTION** set (direct + indirect/document) scored by the vendor Prompt Shields path. A separate **held-out** set of 21 NEW cases (not used while tuning) is reported below.

Two recall views: **strict recall** = the full three-element pattern was asserted (routes to four-eyes). **Attacks routed to review** = strict matches *plus* partial patterns (≥2 of 3 elements) that OPA routes to `ask`; a partial pattern never allows, so near-miss attacks still reach a human.

| Metric | de | en | overall |
|---|---|---|---|
| Label precision (strict) | 1.0 | 1.0 | 1.0 |
| Label recall (strict, full pattern) | 0.8182 | 0.8182 | 0.8182 |
| Attacks routed to review (strict + partial -> ask) | 1.0 | 1.0 | 1.0 |
| Benign false-block rate (strict) | | | 0.0 |
| Benign routed-to-ask rate | | | 0.0625 |
| Semantic path p95 (stages 0-1, ms) | | | 48.313 |
| Semantic path p95 (stages 2-3, ms) | | | TO BE MEASURED |
| Prompt-injection precision (vendor path) | | | TO BE MEASURED |
| Prompt-injection recall (vendor path) | | | TO BE MEASURED |

Held-out set (21 NEW cases, scored separately — the detector was not tuned on these texts):

| Held-out metric | de | en | overall |
|---|---|---|---|
| Label recall (strict) | 0.25 | 0.0 | 0.1111 |
| Attacks routed to review | 0.25 | 0.4 | 0.3333 |
| Benign false-block rate | | | 0.0 |
| Benign routed-to-ask rate | | | 0.0 |

_Source: committed eval run 2026-11-18 14:02 UTC, git `6ead950c`, embedder `st:sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (real multilingual MiniLM model, CPU; see [`eval/results/`](eval/results/))._

> **Honest reading.** This run used the real pinned multilingual MiniLM model (`paraphrase-multilingual-MiniLM-L12-v2`) on CPU. On the tuning set: precision 1.0, strict recall 0.82 (DE and EN alike), and **every attack is routed to a human** (routed-to-review 1.0) via the partial-pattern rule, while benign false-block stays 0.0 and only 6.25% of benign cases are sent to `ask`.
>
> **The honest weakness is generalisation.** On the held-out set — 21 NEW cases the detector was never tuned on — strict recall is only **0.11** and just **0.33** of held-out attacks are routed to review; several new behaviour-source scenarios slip through to `allow`. Precision/false-block stay clean (0 false blocks), so the gap is missed detections, not over-blocking. Next step: expand the exemplar set and legal-element coverage for unseen behaviour sources, and re-measure on held-out before any real use. Do not read the tuning-set numbers as real-world accuracy; the held-out numbers are the more honest indicator.

## Hybrid profile (optional Azure adapters)

The `hybrid` profile adds feature-flagged Azure adapters behind the same adapter interfaces: **Prompt Shields** (Azure AI Content Safety — one jailbreak/injection *signal*, scored separately under a `PROMPT-INJECTION` concept, never a legal verdict), an optional **stage-3 LLM judge** (Azure OpenAI / Foundry, off by default), and an optional **Entra ID** identity provider. All degrade cleanly: no credentials → skipped; a live failure (timeout/401/403/429/5xx) → the tool degrades to `ask`, never a silent allow. Credentials come from environment variables only — no secrets in the repo. Runbook, env vars, cost notes, and the exact command: [`docs/HYBRID.md`](docs/HYBRID.md).

| Hybrid metric | value |
|---|---|
| Prompt Shields precision / recall (scored separately) | TO BE MEASURED |
| Stage 2–3 (vendor/judge) p95 | TO BE MEASURED |

_No hybrid number is published until a real credentialed run exists (see [`docs/HYBRID.md`](docs/HYBRID.md)). A budget alert on the low-cost Azure lab subscription is a prerequisite before any hybrid call._

## Agent security framework

ACA maps onto a three-layer model for securing AI agents — **Information**, **Instructions**, **Actions** — plus a **Testing** discipline. The full mapping gives, for every control, the ACA file that implements it, the test that proves it, and an honest status: [`docs/AGENT-SECURITY-FRAMEWORK.md`](docs/AGENT-SECURITY-FRAMEWORK.md). Status is scoped to **ACA's own code** — controls that belong to the deterministic gateway (a separate repo) are marked Gap (ACA), not credited.

| Layer | Implemented | Partial | Gap |
|---|---|---|---|
| 1 — Information | Log redaction | Context minimization; egress/DLP (signals only) | Least-privilege enforcement; permission-preserving RAG |
| 2 — Instructions | Injection detection (Prompt Shields) | Trusted/untrusted separation; structured extraction (judge); defense-in-depth fallback | — |
| 3 — Actions | Risk-tiered human-in-the-loop (decision tier) | Approver authority (policy changes only) | Tool allowlist; narrow wrappers + backend authz; approval↔args-hash binding |
| Testing | — | Routing/decision evals; model/tool regression (provenance + held-out) | Red-teaming harness (AgentDojo / garak) |

Runtime-hardening gaps are roadmapped to a planned **Agent Hardening Sandbox**; adversarial-testing gaps to the planned **LLM Red-Teaming Pipeline**. Neither is implemented here.

## Limitations

- Lab and synthetic data; mappings are illustrative; no conformity claim and no automation of indeterminate legal concepts.
- Committed metrics use the real multilingual MiniLM model on CPU (`oss` profile); stages 2-3 and vendor paths are not measured on `oss`.
- A low-cost Azure lab subscription with a budget alert gates the hybrid profile, but Prompt Shields / Azure OpenAI / Entra limits are unverified — a budget alert is a prerequisite before any hybrid call ([`docs/DESIGN.md` §15](docs/DESIGN.md)).
- This repo does not implement the sibling projects (audit logging, red-teaming, multi-agent) and does not change the gateway.

## License

See [`LICENSE`](LICENSE).
