# AI Compliance Automation

**Core component: Semantic Guard** — contextual intent labels for prompts, tool calls and artefacts; OPA still decides allow / ask / deny.
**Design note (v0.1)** · Portfolio project by Mir Mansoor Ahmed
**Status:** design · fictional consultancy in examples: *Northwind Advisory* · fictional client: *Halvaro Payments* (~2,000 employees, several sites)
**Umbrella:** AI Governance Platform · sits next to the existing Agent Access Governance Gateway
**Proposed repo (not created):** `ai-compliance-automation`
**Sibling repos (planned, not created):** LLM Red-Teaming Pipeline (`llm-red-teaming-pipeline`) · AI Audit Logging & Monitoring (`ai-audit-logging`) · Multi-Agent AI System (LangGraph) (`langgraph-multi-agent-system`)
**Date:** 14 November 2026 (Europe/Berlin)

This is a lab / portfolio design, not a production product, not legal advice, and not a conformity assessment. Mapping to the EU AI Act or ISO/IEC 27001:2022 is illustrative. Nothing here is a claim that Halvaro Payments, or any real firm, is compliant or audit-ready.

A consulting narrative for the same design lives in [`CASE-STUDY.md`](CASE-STUDY.md).

---

## 1. Problem

Coding agents and cloud chat already sit between Halvaro Payments staff and client or employee data. A deterministic gateway can decide *who* may call *which* tool. It cannot decide whether a request is, in effect, building something the law prohibits — for example a social-scoring workflow typed into Claude Code without using those words.

Law cannot be fully automated. German and EU legal texts use *unbestimmte Rechtsbegriffe* (indeterminate legal concepts) such as *angemessen* and *Stand der Technik*. A machine may flag elements of a requirement. A named human must interpret the hard cases. Only already-interpreted rules should be enforced automatically. Ambiguous requirements go to a four-eyes review. Each human decision becomes a versioned interpretation plus new eval cases, through a pull request, not by the system rewriting policy itself.

The missing piece is this project, **AI Compliance Automation**: a GitHub-native harness whose **core component is the Semantic Guard**. Legal and ISMS requirements live in the repo, a named human records an interpretation, a machine rule (OPA Rego) enforces only that reading, and evidence a reviewer can read is left behind. The Semantic Guard is the contextual layer the deterministic gateway does not have.

---

## 2. Scope and non-scope

**In scope (v1)**

- A requirement map for a small, declared set: EU AI Act Art. 5 (social scoring, and one further prohibited-practice example), a few Art. 9 / 12 / 14 obligations, and a few ISO/IEC 27001:2022 Annex A controls already used for Halvaro Payments in the companion ISMS work. Each entry is labelled `auto`, `human` or `hybrid`.
- Versioned interpretations (owner, reason, review) that are the only source of hard deny rules.
- A **Semantic Guard** that emits intent *labels* and confidence, never a verdict. OPA decides `allow` / `ask` (four-eyes) / `deny`.
- Contextual detection against legal-element rubrics and exemplars (not hard-coded keyword lists), with a deterministic fallback.
- An HTTP contract the Agent Access Governance Gateway can call on the slow path for suspicious or risky tool calls.
- Artefact / PR analysis for the same legal elements in code and diffs.
- A GitHub Actions harness: `opa test`, a labelled eval set, a coverage report, and `make report` (PDF).
- A hybrid demo profile that can use a Microsoft / Azure student account where that is realistic, and a default profile that runs fully open source with no cloud account.

**Out of scope (v1)**

- Replacing the gateway PEP, rewriting `src/apm_cli/**`, or opening a PR to `microsoft/apm`.
- Building the **AI Audit Logging & Monitoring** store (`ai-audit-logging`) or the **LLM Red-Teaming Pipeline** (`llm-red-teaming-pipeline`). This repo *emits* OTel spans the audit-logging sibling will consume later, and *produces* eval cases that pipeline can import later. The **Multi-Agent AI System (LangGraph)** (`langgraph-multi-agent-system`) is a later sibling and is out of scope for this repo.
- A full ISO/IEC 42001 Annex A mapping (the standard text is not in hand; theme-level mentions only).
- Certifying Halvaro Payments, automating Legal's sign-off, or treating the judge model as an authorization control.
- Production high availability, multi-region residency cut-over, or designing the system around a second cloud account. A placeholder adapter slot is reserved; it is not implemented.
- Real client data, live attacks, employer branding (including Telekom / Magenta), or any `Co-authored-by` / AI attribution in commits.

---

## 3. Design principles

1. **Requirement → interpretation → rule → evidence.** Source text and a citation are recorded first. A named human writes a versioned interpretation (owner, reason). Only then is a Rego rule allowed to auto-deny. Evidence points back at the requirement, the interpretation revision, and the rule bundle.
2. **Labels, not verdicts.** The Semantic Guard and artefact analyser return `{concept_id, elements_met[], confidence, evidence_refs[], detector_versions{}}`. OPA is the only decision point, shared with the gateway.
3. **Fail-safe, not fail-open, on the slow path.** If the Guard is down or times out, the deterministic gateway path still runs. Risky tools degrade to `ask`, never to a silent allow. `log-only` rules may fail open.
4. **No self-modifying policy.** Human decisions become YAML and eval fixtures through a PR with four-eyes review. CI must pass before a rule is enforced.
5. **Hybrid, portable by default.** Microsoft services are optional adapters behind feature flags, used in a hybrid demo when credentials exist. `make demo` and CI must pass with the open-source profile alone.
6. **Privacy by default.** Decision records use a pseudonymised subject. They do not carry clear `agent.id`, role or department, and they do not store raw prompt bodies by default.

---

## 4. Architecture

![Architecture — AI Compliance Automation and its core Semantic Guard on the slow path, with the existing gateway as the PEP](diagrams/architecture.png)

*Mermaid source: [`diagrams/architecture.mmd`](diagrams/architecture.mmd). Green / solid = already in the gateway. Blue / dashed = this design. Amber = human. Grey = existing tools we integrate.*

**How to read it.** Staff requests still hit the existing gateway (allowlist, groups, drift pin, approval tiers). Only suspicious or risky tool calls, plus PR artefacts, enter **AI Compliance Automation**. The **Semantic Guard** (the core component) labels the request. OPA decides. Ambiguous cases go to a named reviewer. The reviewer's decision is a new interpretation and new eval cases, merged through CI, not written back by the service itself. Spans go out over OpenTelemetry, with pseudonymised identity, for **AI Audit Logging & Monitoring** to store later.

**Two demo profiles** (feature flags, same code path):

| Profile | When | Identity | Semantic Guard | Optional judge model | Evidence |
|---|---|---|---|---|---|
| `oss` (default) | CI, offline `make demo`, no cloud account | Keycloak (already the gateway lab default) | Local embeddings against curated exemplars, plus deterministic stage-0 signals | Off, or a local stub | OTel → file export; optional self-hosted Langfuse |
| `hybrid` | Optional demo when Azure credentials are present | Entra ID groups (adapter) | Azure AI Content Safety Prompt Shields as one adapter, *in addition to* the local path | Azure OpenAI or Azure AI Foundry, if available | Same OTel contract |

A second cloud adapter slot (possibly AWS; the account is unconfirmed) is reserved in the same interface and left unused. The design does not depend on it.

The lab account is **Azure for Students**, with **USD $90** credit, expiry **7 November 2027**, in the **IU tenant** (verified in the Azure portal on 14 November 2026, Europe/Berlin). Prompt Shields, Azure OpenAI / Foundry access, Entra group-claim limits, region and quota are still **unverified** — see §15. Set a budget alert before any `hybrid` calls. Until those checks pass, `oss` is the profile CI guarantees.

---

## 5. Data model

Four records, all versioned in Git except evidence (which is emitted at runtime).

### 5.1 Requirement

YAML under `requirements/`. One file per requirement.

| Field | Meaning |
|---|---|
| `id` | Stable id, e.g. `REQ-AIA-5-1-c` |
| `source` | `EU AI Act` or `ISO/IEC 27001:2022` |
| `citation` | Article or Annex A id only, e.g. `Art. 5(1)(c)`, `A.8.15` |
| `title` | Short title in our own words — never copied legal text |
| `mode` | `auto` · `human` · `hybrid` |
| `owner` | Role accountable for the mapping (e.g. `ai-governance-lead`) |
| `status` | `active` · `draft` · `retired` |
| `elements` | Optional list of legal or control elements the Guard or a reviewer must consider |
| `rule_ref` | Path to Rego or data file, only when `mode` is `auto` or `hybrid` and an interpretation exists |

### 5.2 Interpretation

YAML under `interpretations/`. Immutable once approved; a change is a new `version`.

| Field | Meaning |
|---|---|
| `id` / `version` | e.g. `INT-2026-001` / `1` |
| `requirement_id` | Foreign key |
| `decision` | `confirmed_prohibited_pattern` · `not_in_scope` · `needs_review` |
| `owner` | Named role of the interpreter |
| `reason` | Why this reading was taken, in the author's words |
| `effective_from` / `review_by` | Dates |
| `rule_ref` | Rego / data that may now auto-enforce this reading |
| `eval_cases` | Paths of fixtures added in the same PR |
| `status` | `draft` · `approved` |

Hard `deny` for a legal concept is allowed only when an *approved* interpretation with `decision: confirmed_prohibited_pattern` is in the signed policy data.

### 5.3 Rule

OPA Rego plus signed data (`thresholds`, `confirmed_prohibited_patterns`, exemplar ids). The same logical policy is what CI tests and what the gateway's PDP evaluates when labels are present. Illustrative shape (not in a repo yet):

```rego
package compliance.tier

# Strictest matching outcome wins. Thresholds and confirmed patterns
# come from signed data, changed only by PR + four-eyes.
tier := "deny" if {
  some l in input.labels
  l.pattern_id in data.confirmed_prohibited_patterns
} else := "four-eyes" if {
  some l in input.labels
  l.concept_id == "AIA-5-1-c"
  l.confidence >= data.thresholds["AIA-5-1-c"].high
  count(l.elements_met) >= 4
} else := "ask" if {
  some l in input.labels
  l.concept_id == "AIA-5-1-c"
  l.confidence >= data.thresholds["AIA-5-1-c"].low
} else := "allow"
```

### 5.4 Evidence

One OpenTelemetry span per decision, aligned with the platform **decision-record v1** contract: `ts`, `decision_id`, `bundle_revision`, `pep=semantic`, `subject_pseudonym`, `groups`, `site`, `resource`, `action`, `tier`, `allowed`, `reason_code`, `labels[]`, `args` (key names, count, SHA-256 only), `latency_ms`, `approver_pseudonyms[]`. No clear `agent.id` / role / department. No raw prompt body by default. **AI Audit Logging & Monitoring** (`ai-audit-logging`) is the later system of record; this repo only emits the span.

---

## 6. Requirement map (v1 starter set)

Illustrative only. Titles are in our own words. ISO 27001 titles follow the Halvaro Payments catalog used in `iso27001-evidence-as-code` (identifiers plus short titles, not standard text).

| ID | Citation | Title (own words) | Mode | v1 handling |
|---|---|---|---|---|
| `REQ-AIA-5-1-c` | EU AI Act Art. 5(1)(c) | Social scoring of natural persons | hybrid | Guard labels the legal elements. Confirmed patterns may deny. Otherwise four-eyes. |
| `REQ-AIA-5-1-f` | EU AI Act Art. 5(1)(f) | Emotion inference at work | hybrid | Same pattern, smaller exemplar set. |
| `REQ-AIA-9` | EU AI Act Art. 9 | A documented risk-management process | human | Recorded in the map. No auto decision. Coverage report counts it as human. |
| `REQ-AIA-12` | EU AI Act Art. 12 | Automatic event logs for traceability | auto | Evidence spans must contain the required fields; CI checks completeness. |
| `REQ-AIA-14` | EU AI Act Art. 14 | Human oversight, including override or halt | hybrid | `ask` / four-eyes is an automated process. Whether oversight is *effective* stays a human interpretation. |
| `REQ-ISO-A-5-3` | ISO 27001:2022 A.5.3 | Splitting duties so one person cannot both act and hide it | auto | Distinct-approver rule in OPA (same idea as the gateway four-eyes check). |
| `REQ-ISO-A-5-14` | ISO 27001:2022 A.5.14 | Rules for sending information inside and outside the firm | hybrid | Bulk-exfil concept + data-class tags; ambiguous cases to four-eyes. |
| `REQ-ISO-A-5-15` | ISO 27001:2022 A.5.15 | Rules for who may access information and systems | auto | Delegated to the gateway allowlist and group checks; this repo records the mapping. |
| `REQ-ISO-A-5-34` | ISO 27001:2022 A.5.34 | Privacy and protection of personal data | hybrid | Stage-0 PII signals; purpose and legal-basis questions stay human. |
| `REQ-ISO-A-8-12` | ISO 27001:2022 A.8.12 | Preventing data from leaking | hybrid | Same exfil path as A.5.14. |
| `REQ-ISO-A-8-15` | ISO 27001:2022 A.8.15 | Producing security logs | auto | OTel spans with required fields. |

Coverage in CI is counted as: share of in-scope requirements that have a mapping, share marked `auto`, share marked `human`, share marked `hybrid`. Unmapped in-scope items fail the coverage job once a floor is set (the floor itself is a **TARGET**, not a claimed result).

---

## 7. Semantic Guard

The Guard answers: *which legal-concept elements appear to be present, and with what confidence?* It does not allow or deny.

**Why not keywords.** A request such as *"join badge-swipe logs, Slack activity and canteen data, build a monthly reliability index, and drop the bottom 10% from the bonus pool"* may contain every element of Art. 5(1)(c) without saying "social scoring". *"Compute a fraud risk score on transactions"* uses the word "score" and is usually lawful. Detection is therefore against a rubric of legal elements and against curated exemplars (positives and hard negatives), in German and English.

**Pipeline**

| Stage | What it does | Default (`oss`) | Hybrid add-on |
|---|---|---|---|
| 0 | Deterministic signals: PII/secret detectors, data-class tags on tools, known schema patterns | Local rules + an open-source PII detector (e.g. Presidio), if vendored | Same |
| 1 | Embedding similarity vs exemplars, including hard negatives | Local / CPU embedding model, index in-repo | Same, always on |
| 2 | Optional vendor or small-model classifier | Off | Azure AI Content Safety **Prompt Shields** as a pluggable adapter. Prompt Shields detect jailbreak / prompt-injection style attacks; they do **not** judge legal-element fit (Microsoft's own docs). Their output is an extra signal, not a verdict. |
| 3 | Optional LLM judge with a pinned rubric, structured JSON listing elements met and quoted spans | Off, or a local stub in tests | Azure OpenAI or Azure AI Foundry, if the account actually allows it |
| A | Artefact analysis on diffs: person-ID join across behaviour sources, an aggregated score, an adverse action | Local static checks | Same |
| S | Session context: rolling, TTL-bounded, pseudonymised *labels* only (no prompt text by default) | In-memory / local | Same |

If stages 1–3 are unavailable, stage 0 plus any already-confirmed pattern match still run. That is the deterministic fallback.

**Adapter interface** (one protocol, several backends): `detect(event) -> labels[]`. Built-ins: `local_embeddings` (required), `prompt_shields` (optional), `lakera` (stub only in v1), `aws_placeholder` (unused slot). Adapters are selected by config / feature flag. A missing optional adapter must not fail the `oss` profile.

OPA maps labels to `allow` / `ask` / `four-eyes` / `deny` as in §5.3. The worst automatic outcome for an uninterpreted concept is "pause and ask a human".

---

## 8. Buy vs. Build

| Component | Microsoft-native | Commercial | Open-source | We build | Chosen in demo |
|---|---|---|---|---|---|
| Identity / groups | Entra ID | Okta and others | Keycloak | Only the adapter that normalises claims | **`oss`:** Keycloak. **`hybrid`:** Entra ID, if the student tenant can issue group claims (unverified). |
| Semantic / injection filter | Azure AI Content Safety Prompt Shields | Lakera (or successor brand) | Local embeddings, Presidio, optional Llama Guard (licence to be re-checked before use) | The legal-element rubric, exemplar set, label schema, and artefact checks | **`oss`:** local embeddings + stage 0. **`hybrid`:** Prompt Shields *plus* the local path. Lakera remains a stub. |
| Judge model | Azure OpenAI / Azure AI Foundry | Other hosted models | Local stub; no judge required to demo | The pinned rubric and the parser for structured output | **`oss`:** judge off. **`hybrid`:** Azure OpenAI or Foundry *if* access exists; otherwise the demo still runs without it. |
| Policy decision | Copilot / Purview / Entra policy (siloed, not a cross-tool PDP) | Several GRC suites | **OPA / Rego** | Requirement and interpretation YAML, and the Rego that consumes labels | **OPA in both profiles.** |
| Requirement register | Compliance Manager / Purview | OneTrust, Credo AI, IBM watsonx.governance | YAML in Git | The map, coverage report, and interpretation workflow | **Git YAML in both profiles.** A vendor register is a future adapter, not v1. |
| Evidence / traces | M365 / Azure audit logs | SIEM products | **OpenTelemetry**, optional self-hosted Langfuse | The decision-record mapping and the PDF coverage / evidence report | **OTel in both profiles.** Langfuse optional. **AI Audit Logging & Monitoring** is a sibling. |
| Human approval | Power Automate / tickets (not used here) | Jira / ServiceNow | CLI in the existing gateway | Four-eyes recording that writes an interpretation PR + eval cases | Gateway-style CLI in v1; ticket adapter later. |

**Why hybrid, not "Azure-only" or "OSS-only".** Commodity filters and an IdP are things a firm often already licenses. The differentiated work is the requirement-to-rule pipeline, the legal-element labels, the four-eyes interpretation log, and the evidence pack. Those stay ours, and they stay cloud-agnostic. Prompt Shields are useful and honestly limited: they are not a substitute for Art. 5 element detection. Entra is useful when group claims are available, and Keycloak keeps the lab reproducible without a cloud login.

---

## 9. Integration with the gateway and AI Audit Logging & Monitoring

- The gateway remains the PEP. On the slow path it calls **AI Compliance Automation** (the Semantic Guard API) over a versioned HTTP API (`POST /v1/labels`) with tool metadata, a session-label summary, and (in memory only) the prompt or argument text needed to classify. The Guard's response is the label schema in §5.4. OPA in the gateway takes the final decision.
- For demos and CI, a recorded fixture mode returns committed labels so `make demo` does not need a live gateway or a live Azure call.
- **Fail-safe:** Guard timeout or 5xx → deterministic checks still apply; tools in a `risky` class are forced to `ask`; never a silent allow.
- Evidence: both the gateway decision and the Semantic Guard's label call emit OTel spans with `subject_pseudonym`. **AI Audit Logging & Monitoring** consumes them later; this repo does not store a long-term log.
- This repo does not change the public `agent-trust-gateway` and does not edit `src/apm_cli/**` on the APM fork.

---

## 10. GitHub-native harness

The repo *is* the compliance register.

- `requirements/*.yaml` and `interpretations/*.yaml` are validated against a JSON Schema.
- CI on every PR: schema validation, `opa test`, the eval set (attack, benign, ambiguous; DE and EN), and a coverage report (`% mapped`, `% auto`, `% human`, `% hybrid`).
- Approved interpretations and their eval cases land in the same PR, reviewed by CODEOWNERS (four-eyes).
- `make report` builds a PDF: the map, coverage, latest committed eval results (or "not measured"), and a short decision log excerpt from fixture spans. The renderer fails closed if required fields are missing.
- `make demo` runs the script in §12 in under 15 minutes, defaulting to the `oss` profile.

---

## 11. Eval plan *(TARGETS — nothing measured yet)*

No number in a README, report or CV bullet may be invented. Every figure must come from a committed eval run with timestamp and git SHA. Until then, write **TARGET** or "to be measured".

| Metric | What will be measured | TARGET (design budget, not a result) |
|---|---|---|
| Label precision / recall | On a labelled set: attack, benign, and ambiguous cases, reported **separately for German and English** | Set after a first committed run; no floor is claimed now |
| Benign false-block rate | Human-labelled false denies on the benign path | To be measured; must be published next to precision/recall |
| Fast-path p95 | Gateway allow-path decision *without* the Guard (existing harness, after any PDP change) | Re-use the gateway harness; do not restate old numbers as this project's results |
| Semantic-path p95 | Stages 0–1, and separately stages 2–3 when they run | Design budgets in the platform note were ≤ 30 ms (stages 0–1) and ≤ 1.5 s (judge on human-tier flows). **Re-measure here. Do not quote those budgets as results.** |
| Coverage | `% mapped` / `% auto` / `% human` / `% hybrid` on the v1 set | Floor set once the starter map is encoded in YAML |

The eval set must include hard negatives (lawful fraud or credit scoring) and at least one multi-turn "salami" case. Vendor adapters, when present, are scored *separately* from the local path, so a Prompt Shields miss is not hidden inside a blended number.

---

## 12. Demo script (`make demo`, under 15 minutes)

Fictional setting: Northwind Advisory running the harness for Halvaro Payments. Synthetic data only. Default profile: `oss`. The same three scenarios must also run under `hybrid` when credentials exist.

1. **Clear deny — social scoring, no keyword.** A Claude Code-style prompt joins employee behaviour sources, builds a reliability index, and applies an adverse HR action. An approved interpretation already records this as a confirmed Art. 5(1)(c) pattern, *or* the Guard finds enough elements at high confidence against that confirmed pattern. OPA returns `deny`. A span is written. The report shows the requirement, the interpretation, and the deny.
2. **Ambiguous request → four-eyes → a new rule.** A second prompt hits some, but not all, elements (or sits between thresholds). OPA returns `ask` / four-eyes. A reviewer records an interpretation (`owner`, `reason`) and adds eval cases. A PR is opened; CI runs `opa test`, the eval set, and coverage. After (simulated) merge, a replay of the same prompt follows the new interpreted rule. Policy was not self-modified.
3. **Benign allow.** "Compute a fraud risk score on transactions" (a hard negative) is allowed. The span shows `allow` and the coverage report still lists Art. 5 as hybrid, not as a blanket keyword block.

`make report` is the last step and produces the PDF.

---

## 13. Risks

| Risk | Mitigation |
|---|---|
| False blocks push staff to shadow AI | Log-only / ask first for uninterpreted concepts; publish false-block rate once measured; fast appeal path |
| Judge or vendor model drift | Pin versions; golden-set gate on upgrades; `oss` path does not depend on the vendor |
| Student-account features missing or region-locked | Feature flags; `oss` is the supported default; limits listed as a TODO in §15, not assumed |
| Treating Prompt Shields as a legal classifier | Adapter docs and the report must state Microsoft's own limit: it does not judge policy compliance or task alignment |
| Works-council concern if employees are identifiable in logs | Pseudonymisation, no prompt bodies by default, aggregate reports; a Betriebsvereinbarung is a client legal step, not something this lab "implements" |
| Over-claiming compliance | Disclaimers on the map, the report, the README, and the case study |

---

## 14. CV angle

Do not use these bullets until the repo exists and, for any number, a committed eval exists. Suggested framing after implementation (metrics still **to be measured**):

- Designed a GitHub-native compliance harness that turns a legal or ISMS requirement into a versioned human interpretation, an OPA rule, and evidence, without automating indeterminate legal concepts.
- Built a Semantic Guard that labels contextual intent (legal elements, exemplars in DE/EN) and leaves allow / ask / deny to OPA; integrated it as the slow path of an existing MCP gateway, fail-safe to `ask` on Guard failure.
- Used a hybrid, adapter-based stack: Keycloak + local embeddings + OPA + OpenTelemetry by default; optional Entra ID, Azure Prompt Shields, and Azure OpenAI / Foundry behind feature flags so the same demo runs fully offline.

Limits to say out loud: lab and synthetic data; mappings are illustrative; Azure for Students credit and expiry are known, but Prompt Shields / Azure OpenAI limits are not yet checked; no conformity claim.

---

## 15. Azure student account (verified facts and remaining TODOs)

**Verified in the Azure portal on 14 November 2026 (Europe/Berlin):** the lab subscription is **Azure for Students**, with **USD $90** credit, expiring **7 November 2027**, in the **IU tenant**.

The `hybrid` profile may use this account. The `oss` profile remains the one CI guarantees, and `make demo` must still run with no Azure credentials.

**Do now**

- [ ] **Set a budget alert** on this subscription before any `hybrid` traffic (Prompt Shields, Azure OpenAI / Foundry, or other billed APIs). Suggested thresholds: 50% and 80% of the USD $90 credit, delivered to an address Mir monitors. Do not turn on paid adapters until the alert is confirmed.

**Still unverified (TODOs)**

- [ ] Whether a directory / app registration is allowed on this student tenant, and whether **Entra ID** can issue group claims to a lab app (including any P1/P2 or student-plan limits).
- [ ] Whether **Azure AI Content Safety / Prompt Shields** is available in an EU region, what the quota is, and how much of the USD $90 credit a demo run consumes.
- [ ] Whether **Azure OpenAI** and / or **Azure AI Foundry** access is granted, which models and regions, and at what quota. Access is often a separate approval.
- [ ] Rate limits, logging and retention defaults (no prompt bodies should be sent to a vendor unless the flag is explicit).
- [ ] A possible **second cloud account** (maybe AWS): confirm it exists before doing any work; keep it as an unused adapter slot until then.

---

## 16. Limits and sources

- No Semantic Guard or requirement harness exists in code yet. Precision, recall, false-block rate and latency are **unknown**.
- Art. 12 / 14 duties attach mainly to high-risk systems and to providers; whether they apply to a given Halvaro Payments assistant is a legal classification, not a finding of this design.
- ISO/IEC 42001 is mentioned only at theme level. ISO 27001 titles are our own words from the Halvaro Payments catalog.
- Prompt Shields behaviour is taken from Microsoft Learn (retrieved for the platform research on 11–12 Nov 2026) and must be re-checked at implementation time.
- This document does not create a GitHub repository.

*Sources: platform `system-design.md` and `production-research.md` (11–12 Nov 2026); gateway `DESIGN.md`; Halvaro Payments ISMS brief and the `iso27001-evidence-as-code` Annex A catalog (ids + short titles). EU AI Act Service Desk Art. 5, 9, 12, 14 (consolidated text as at 27 July 2026). Design date: 14 Nov 2026, Europe/Berlin.*
