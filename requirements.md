# Requirements — AI Compliance Automation

**Core component: Semantic Guard** (emits contextual intent labels + confidence; OPA decides allow / ask / four-eyes / deny).

Product brief: [`docs/DESIGN.md`](docs/DESIGN.md). Narrative context only: [`docs/CASE-STUDY.md`](docs/CASE-STUDY.md). Architecture diagram: [`docs/diagrams/architecture.png`](docs/diagrams/architecture.png).

Fictional consultancy **Northwind Advisory**; fictional client **NordPay** (~2,000 employees, several sites). Synthetic data only. No employer branding. No AI commit attribution. Never invent metrics (every number comes from a committed eval run with timestamp + git SHA, else `TARGET` / `TO BE MEASURED`). Never copy statute or standard text (IDs + short titles in our own words, illustrative mappings only).

This is a lab / portfolio project, not a product, not legal advice, and not a conformity assessment.

---

## Glossary

- **Requirement** — a versioned YAML record of a legal/ISMS obligation (source + citation + short title + mode).
- **Interpretation** — a versioned, human-authored reading of a requirement (owner, reason, decision). The *only* source of a hard `deny`.
- **Semantic Guard** — the core component. Emits `labels[]` (legal-concept elements present + confidence + evidence refs + detector versions). Never a verdict.
- **Label** — `{concept_id, pattern_id?, elements_met[], confidence, evidence_refs[], detector_versions{}}`.
- **OPA / PDP** — the only decision point. Maps labels → `allow` | `ask` | `four-eyes` | `deny`.
- **PEP** — the existing Agent Access Governance Gateway (out of scope to change). Calls the Guard on the slow path.
- **Profile** — `oss` (default, no cloud; CI must pass here) or `hybrid` (feature-flagged Azure adapters).
- **Four-eyes** — a human review that records an interpretation + eval cases via PR (two distinct approvers).
- **Fixture mode** — recorded labels/spans so `make demo` and CI run with no live gateway and no cloud call.

---

## EARS acceptance criteria conventions

Criteria use EARS keywords: **WHEN** (event), **WHILE** (state), **IF** (condition), **THE SYSTEM SHALL** (required behaviour). Each story lists numbered, testable criteria.

---

## R1 — Requirement register

**As** the AI governance lead, **I want** each in-scope legal/ISMS obligation recorded as a versioned YAML requirement, **so that** the repo itself is the compliance register and every rule traces back to a source.

Acceptance criteria:
1. THE SYSTEM SHALL store one requirement per file under `requirements/*.yaml` with fields `id`, `source`, `citation`, `title`, `mode`, `owner`, `status`, optional `elements`, optional `rule_ref` (per DESIGN.md §5.1).
2. WHEN a requirement file is validated, THE SYSTEM SHALL check it against a JSON Schema and fail validation IF a required field is missing or an enum value is invalid (`source` ∈ {EU AI Act, ISO/IEC 27001:2022}; `mode` ∈ {auto, human, hybrid}; `status` ∈ {active, draft, retired}).
3. THE SYSTEM SHALL encode the v1 starter map from DESIGN.md §6 as requirement files: `REQ-AIA-5-1-c`, `REQ-AIA-5-1-f`, `REQ-AIA-9`, `REQ-AIA-12`, `REQ-AIA-14`, `REQ-ISO-A-5-3`, `REQ-ISO-A-5-14`, `REQ-ISO-A-5-15`, `REQ-ISO-A-5-34`, `REQ-ISO-A-8-12`, `REQ-ISO-A-8-15`, each with its listed mode.
4. THE SYSTEM SHALL use titles written in our own words and SHALL NOT reproduce statute or standard text.
5. IF a requirement sets `rule_ref`, THEN THE SYSTEM SHALL require `mode` to be `auto` or `hybrid` and an approved interpretation to exist, else validation fails.

## R2 — Interpretation register (human-authored, versioned)

**As** a named interpreter, **I want** my reading of a requirement recorded as an immutable, versioned interpretation, **so that** auto-enforcement only ever reflects a decision a human owns.

Acceptance criteria:
1. THE SYSTEM SHALL store interpretations under `interpretations/*.yaml` with fields `id`, `version`, `requirement_id`, `decision`, `owner`, `reason`, `effective_from`, `review_by`, optional `rule_ref`, optional `eval_cases`, `status` (per DESIGN.md §5.2).
2. THE SYSTEM SHALL validate `decision` ∈ {confirmed_prohibited_pattern, not_in_scope, needs_review} and `status` ∈ {draft, approved}, and SHALL require `requirement_id` to resolve to an existing requirement.
3. WHILE an interpretation has `status: approved`, THE SYSTEM SHALL treat it as immutable: a change SHALL be recorded as a new `version`, not an edit in place.
4. THE SYSTEM SHALL allow a hard `deny` for a legal concept ONLY WHEN an approved interpretation with `decision: confirmed_prohibited_pattern` is present in the signed policy data (per DESIGN.md §5.2 / §5.3).
5. WHEN an interpretation references `eval_cases`, THE SYSTEM SHALL require each referenced fixture path to exist in the same change set.

## R3 — Semantic Guard core (stages 0–1, labels only)

**As** the platform, **I want** the Semantic Guard to label which legal-concept elements appear present and with what confidence, **so that** OPA — not the Guard — can decide, and so that detection is contextual rather than keyword-based.

Acceptance criteria:
1. THE SYSTEM SHALL expose `detect(event) -> labels[]` and SHALL return labels matching the schema in DESIGN.md §5.4 (`concept_id`, optional `pattern_id`, `elements_met[]`, `confidence`, `evidence_refs[]`, `detector_versions{}`).
2. THE SYSTEM SHALL NOT return an authorization verdict (`allow`/`deny`) from the Guard; the Guard returns labels only.
3. THE SYSTEM SHALL run stage 0 (deterministic signals: PII/secret detectors, data-class tags, known schema patterns) and stage 1 (local embedding similarity vs curated exemplars including hard negatives) in the `oss` profile with no cloud dependency.
4. THE SYSTEM SHALL ship curated exemplars for the Art. 5(1)(c) social-scoring concept in **both German and English**, including positives and hard negatives (e.g. lawful fraud/credit scoring).
5. WHEN detecting against a concept, THE SYSTEM SHALL score against a rubric of legal elements and exemplars, and SHALL NOT rely on a hard-coded keyword list as the decision basis.
6. THE SYSTEM SHALL analyse code/diff artefacts (stage A) for the social-scoring elements: a person-ID join across behaviour sources, an aggregated score, and an adverse action.
7. THE SYSTEM SHALL keep session context (stage S) as rolling, TTL-bounded, pseudonymised **labels only**, and SHALL NOT store raw prompt text by default.
8. THE SYSTEM SHALL record `detector_versions` on every label so results are reproducible and auditable.

## R4 — Adapter interface and profiles

**As** a maintainer, **I want** Guard backends behind one adapter interface selected by feature flags, **so that** the same code path runs offline (`oss`) or with optional cloud signals (`hybrid`) and degrades cleanly.

Acceptance criteria:
1. THE SYSTEM SHALL define a single adapter protocol `detect(event) -> labels[]` with backends `local_embeddings` (required), `prompt_shields` (optional), `lakera` (stub only in v1), `aws_placeholder` (unused slot).
2. THE SYSTEM SHALL select adapters by config / feature flag and default to the `oss` profile.
3. WHILE the `oss` profile is active, THE SYSTEM SHALL run and pass CI with all optional adapters absent, and an absent optional adapter SHALL NOT fail the build or a request.
4. WHEN an optional adapter's credentials are missing, THE SYSTEM SHALL degrade cleanly (skip that signal, log the skip) rather than error the request.
5. THE SYSTEM SHALL score any vendor adapter's output **separately** from the local path in eval reporting, so a vendor miss is never hidden inside a blended number.
6. THE SYSTEM SHALL document that Azure AI Content Safety Prompt Shields detect jailbreak / prompt-injection patterns and do **not** judge legal-element fit; its output is one signal, not a verdict.

## R5 — Optional stage-3 judge adapter (off by default)

**As** a maintainer, **I want** an optional pinned LLM judge adapter, **so that** a hybrid demo can add structured legal-element analysis without the core depending on it.

Acceptance criteria:
1. THE SYSTEM SHALL provide a stage-3 judge adapter targeting Azure OpenAI or Azure AI Foundry that is **off by default**.
2. WHEN the judge runs, THE SYSTEM SHALL use a pinned model/version and a pinned rubric, and SHALL parse structured JSON (elements met + quoted spans) into labels.
3. IF the judge is unavailable or credentials are missing, THEN THE SYSTEM SHALL fall back to stages 0–1 (plus any confirmed pattern) and SHALL NOT fail the request.
4. THE SYSTEM SHALL provide a local stub judge usable in tests so judge-path logic is testable offline.

## R6 — OPA decision policy

**As** the platform, **I want** OPA to map labels, confirmed patterns, and thresholds to a tier, **so that** there is a single decision point shared with the gateway.

Acceptance criteria:
1. THE SYSTEM SHALL implement Rego that maps `input.labels`, `data.confirmed_prohibited_patterns`, and `data.thresholds` to `allow` | `ask` | `four-eyes` | `deny` following the shape in DESIGN.md §5.3.
2. THE SYSTEM SHALL return `deny` ONLY WHEN a label's `pattern_id` is in `data.confirmed_prohibited_patterns` (which is only populated via an approved `confirmed_prohibited_pattern` interpretation).
3. WHEN labels match a concept at high confidence with enough elements met but no confirmed pattern, THE SYSTEM SHALL return `four-eyes`; at low-but-present confidence it SHALL return `ask`; otherwise `allow` (strictest matching outcome wins).
4. THE SYSTEM SHALL source `thresholds` and `confirmed_prohibited_patterns` only from signed policy data changed via PR + four-eyes, and SHALL NOT allow runtime mutation of that data.
5. THE SYSTEM SHALL have `opa test` cases covering each outcome (deny, four-eyes, ask, allow) that pass in CI.

## R7 — Label HTTP API and fixture mode

**As** the gateway (PEP), **I want** a versioned HTTP endpoint to request labels on the slow path, **so that** suspicious/risky tool calls and PR artefacts can be classified, with an offline fixture mode for demo/CI.

Acceptance criteria:
1. THE SYSTEM SHALL expose `POST /v1/labels` accepting tool metadata, a session-label summary, and (in memory only) the text needed to classify, and SHALL respond with the label schema in DESIGN.md §5.4.
2. THE SYSTEM SHALL version the API path (`/v1/`) and SHALL document the request/response contract.
3. WHILE fixture mode is enabled, THE SYSTEM SHALL return committed recorded labels and SHALL NOT require a live gateway or any cloud call.
4. THE SYSTEM SHALL NOT persist raw prompt/argument bodies from a request by default.

## R8 — Fail-safe behaviour

**As** a security owner, **I want** the Guard's absence to never produce a silent allow, **so that** a Guard outage degrades to asking a human, not to bypassing control.

Acceptance criteria:
1. WHEN the Guard times out or returns a 5xx, THE SYSTEM SHALL leave the deterministic gateway path unaffected.
2. WHILE the Guard is unavailable, THE SYSTEM SHALL force tool calls in the `risky` class to `ask` and SHALL NOT return a silent `allow`.
3. THE SYSTEM SHALL allow `log-only` rules to fail open, and SHALL document which classes fail open vs. fail-safe.
4. THE SYSTEM SHALL have tests for the "adapter absent", "Guard timeout", and "Guard 5xx" paths asserting no silent allow.

## R9 — Four-eyes review and feedback loop

**As** a reviewer, **I want** an ambiguous decision to become a new interpretation + eval cases via a PR, **so that** policy is changed by humans through review, never by the running system.

Acceptance criteria:
1. WHEN a decision is `ask` / `four-eyes`, THE SYSTEM SHALL provide a flow that records `owner`, `reason`, and `decision`.
2. THE SYSTEM SHALL produce (or update) a PR that adds an interpretation YAML and the associated eval case fixtures in the same change set.
3. THE SYSTEM SHALL NOT write policy, interpretations, confirmed patterns, or thresholds at runtime (no self-modifying policy).
4. THE SYSTEM SHALL require two distinct approvers (CODEOWNERS four-eyes) before an interpretation's eval cases and rule can be enforced.
5. WHEN the same prompt is replayed after a (simulated) merge, THE SYSTEM SHALL follow the newly interpreted rule.

## R10 — Evidence spans (privacy by default)

**As** an auditor, **I want** one OpenTelemetry span per decision aligned with the decision-record contract, **so that** a sibling audit-logging system can store traceable, privacy-preserving evidence.

Acceptance criteria:
1. WHEN a decision is made, THE SYSTEM SHALL emit one OTel span carrying the decision-record v1 fields in DESIGN.md §5.4 (`ts`, `decision_id`, `bundle_revision`, `pep=semantic`, `subject_pseudonym`, `groups`, `site`, `resource`, `action`, `tier`, `allowed`, `reason_code`, `labels[]`, `args`, `latency_ms`, `approver_pseudonyms[]`).
2. THE SYSTEM SHALL use a pseudonymised subject and SHALL NOT include clear `agent.id`, role, or department.
3. THE SYSTEM SHALL record `args` as key names, count, and SHA-256 only, and SHALL NOT store raw prompt bodies by default.
4. THE SYSTEM SHALL emit spans to a file exporter in `oss`, and SHALL NOT itself act as a long-term log store.

## R11 — CI: schema, policy, eval, coverage

**As** a maintainer, **I want** CI to validate schemas, run policy tests, run the eval set, and report coverage, **so that** a rule cannot be enforced until it passes review gates.

Acceptance criteria:
1. ON every PR, THE SYSTEM SHALL run: requirement/interpretation JSON Schema validation, `opa test`, the eval set, and the coverage report.
2. THE SYSTEM SHALL run the eval set across categories attack, benign, and ambiguous, in both German and English.
3. THE SYSTEM SHALL produce a coverage report with `% mapped`, `% auto`, `% human`, `% hybrid` over the in-scope set.
4. WHEN a coverage floor is configured, THE SYSTEM SHALL fail the coverage job IF an in-scope requirement is unmapped below the floor (the floor is a TARGET, not a claimed result).
5. THE SYSTEM SHALL pass all CI jobs using the `oss` profile with optional adapters absent.

## R12 — Eval runner and metrics discipline

**As** the project owner, **I want** metrics measured and persisted with provenance, **so that** no number is ever invented.

Acceptance criteria:
1. THE SYSTEM SHALL measure label precision/recall **per language** (DE and EN), benign false-block rate, and semantic-path p95 for stages 0–1 and (separately) stages 2–3 when they run.
2. WHEN an eval run completes, THE SYSTEM SHALL persist results with a timestamp and the git SHA of the run.
3. WHILE no committed run exists for a metric, THE SYSTEM SHALL display it as `TARGET` / `TO BE MEASURED` in README, report, and docs.
4. THE SYSTEM SHALL include hard negatives (lawful fraud/credit scoring) and at least one multi-turn "salami" case in the eval set.
5. THE SYSTEM SHALL report vendor-adapter scores separately from the local path.

## R13 — `make report` (PDF, fail closed)

**As** a reviewer, **I want** a readable PDF evidence pack, **so that** the map, coverage, latest eval results, and a decision-log excerpt are reviewable in one artefact.

Acceptance criteria:
1. WHEN `make report` runs, THE SYSTEM SHALL build a PDF containing the requirement map, the coverage figures, the latest committed eval results (or "not measured"), and a short decision-log excerpt from fixture spans.
2. IF a required field for the report is missing, THEN THE SYSTEM SHALL fail closed (error and produce no partial/misleading PDF).
3. THE SYSTEM SHALL include the project disclaimers (lab/synthetic, illustrative mapping, no conformity claim) in the report.

## R14 — `make demo` (15 minutes, oss default)

**As** a reviewer, **I want** a self-contained demo, **so that** the three scenarios run offline in under 15 minutes.

Acceptance criteria:
1. WHEN `make demo` runs with no cloud credentials, THE SYSTEM SHALL complete the three DESIGN.md §12 scenarios in under 15 minutes on the `oss` profile.
2. THE SYSTEM SHALL demonstrate scenario 1: a keyword-free social-scoring prompt → OPA `deny` → a span is written → the report shows requirement + interpretation + deny.
3. THE SYSTEM SHALL demonstrate scenario 2: an ambiguous prompt → `ask`/four-eyes → a recorded interpretation + eval cases → a PR → CI (`opa test`, eval, coverage) → replay follows the new rule, with policy not self-modified.
4. THE SYSTEM SHALL demonstrate scenario 3: the benign "fraud risk score on transactions" hard negative → `allow`, with Art. 5 still listed as hybrid (not a keyword block).
5. WHEN `hybrid` credentials are present, THE SYSTEM SHALL run the same three scenarios under the `hybrid` profile.

## R15 — Identity and Azure prerequisites

**As** a maintainer, **I want** identity to be optional and Azure usage gated by documented prerequisites, **so that** the lab is reproducible and never silently spends credit.

Acceptance criteria:
1. THE SYSTEM SHALL NOT require a cloud IdP; WHERE identity is needed in tests, it SHALL use a Keycloak or fixture token, and Entra ID SHALL be an optional adapter only.
2. THE SYSTEM SHALL document the verified lab account facts (Azure for Students, USD $90, expires 7 November 2027, IU tenant; verified 14 Nov 2026 Europe/Berlin) and the open TODOs from DESIGN.md §15.
3. THE SYSTEM SHALL document that a budget alert is a prerequisite that must be set before any `hybrid` adapter is enabled, and SHALL NOT assume unverified Prompt Shields / Azure OpenAI / Foundry limits.

## R16 — Documentation and boundaries

**As** a reader, **I want** skimmable, honest docs that name the Semantic Guard as the core, **so that** the project is understandable in ~3 minutes and makes no over-claim.

Acceptance criteria:
1. THE SYSTEM SHALL present a README skimmable in ~3 minutes: problem → diagram → Semantic Guard → how to run (`make demo`, both profiles) → results table (when measured) → limitations.
2. THE SYSTEM SHALL name Semantic Guard as the core component in the README title area and in `design.md`.
3. THE SYSTEM SHALL NOT edit `src/apm_cli/**`, open a PR to `microsoft/apm`, or change `agent-trust-gateway`, and SHALL NOT implement the sibling repos (`ai-audit-logging`, `llm-red-teaming-pipeline`, `langgraph-multi-agent-system`).
4. THE SYSTEM SHALL carry disclaimers (lab/synthetic data, illustrative mappings, no conformity claim) in README and report, and SHALL use no employer branding and no AI commit attribution.

---

## Out of scope (v1)

Replacing the gateway PEP; editing `src/apm_cli/**` or PR-ing `microsoft/apm`; building `ai-audit-logging` or `llm-red-teaming-pipeline`; `langgraph-multi-agent-system`; a full ISO/IEC 42001 Annex A mapping; treating a judge/Prompt Shields as an authorization control; production HA, multi-region cut-over, or a second-cloud implementation (slot reserved, unused); real client data; live attacks.

## Traceability to DESIGN.md

- R1/R2 ← §5.1, §5.2, §6, §10
- R3 ← §5.4, §7
- R4/R5 ← §4, §7, §8
- R6 ← §5.3
- R7 ← §9, §10
- R8 ← §3 (principle 3), §9
- R9 ← §3 (principle 4), §10, §12
- R10 ← §5.4, §9
- R11/R12 ← §10, §11
- R13 ← §10, §13
- R14 ← §12
- R15 ← §8, §15
- R16 ← §2, §3, §13, §16
