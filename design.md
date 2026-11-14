# Design — AI Compliance Automation

**Core component: Semantic Guard** — it emits contextual intent *labels* + confidence for prompts, tool calls, and artefacts. **OPA is the only decision point** (allow / ask / four-eyes / deny).

This document is the engineering design for the spec. It aligns with the product brief in [`docs/DESIGN.md`](docs/DESIGN.md) and the architecture diagram in [`docs/diagrams/architecture.png`](docs/diagrams/architecture.png) (Mermaid source [`docs/diagrams/architecture.mmd`](docs/diagrams/architecture.mmd)). Where the two differ, `docs/DESIGN.md` is authoritative for scope and `design.md` is authoritative for build detail.

Lab / portfolio project. Synthetic data only. Illustrative mappings, no conformity claim.

---

## 1. Overview and alignment

The existing **Agent Access Governance Gateway** stays the PEP and the fast path. This repo is a standalone sibling providing the **semantic / contextual slow path**. The gateway calls `POST /v1/labels` for suspicious or risky tool calls and for PR artefacts; the Semantic Guard returns labels; OPA (shared policy shape) decides; an OTel span records the decision.

Design goals, in priority order:
1. **Safety** — fail-safe to `ask`, never a silent allow; no self-modifying policy; privacy by default.
2. **Correctness** — labels trace to legal elements; `deny` only from an approved confirmed pattern; metrics only from committed runs.
3. **Portability** — `oss` profile runs fully offline and is the CI-guaranteed path; cloud is optional behind flags.

```
Gateway (PEP, exists) ──slow path──▶ /v1/labels ──▶ Semantic Guard (stages 0,1,A,S [,2,3])
                                                        │ labels[]
                                                        ▼
                                                      OPA PDP ──▶ allow | ask | four-eyes | deny
                                                        │
                                                        ▼
                                                 OTel span (pseudonymised) ─▶ (ai-audit-logging, later)
```

---

## 2. Component architecture

```
ai-compliance-automation/
├── requirements/                 # R1: one YAML per requirement
├── interpretations/              # R2: versioned, human-authored
├── schemas/                      # R1/R2: JSON Schema for requirement & interpretation
├── policy/                       # R6: Rego + signed data (thresholds, confirmed patterns)
│   ├── tier.rego
│   ├── tier_test.rego
│   └── data/                     # thresholds.json, confirmed_prohibited_patterns.json
├── guard/                        # R3-R8: Semantic Guard service (Python)
│   ├── api/                      # POST /v1/labels, fixture mode
│   ├── adapters/                 # detect(event)->labels[]: local_embeddings, prompt_shields, lakera, aws_placeholder, judge
│   ├── stages/                   # stage0 signals, stage1 embeddings, stageA artefact, stageS session
│   ├── labels/                   # label schema + detector_versions
│   ├── evidence/                 # OTel span emitter (decision-record v1)
│   └── failsafe/                 # risky-class + timeout/5xx handling
├── exemplars/                    # R3: DE+EN positives and hard negatives per concept
├── eval/                         # R12: labelled set + runner + results (with ts + git SHA)
├── review/                       # R9: four-eyes recorder -> interpretation PR + eval cases
├── report/                       # R13: make report -> PDF (fail closed)
├── fixtures/                     # R7/R14: recorded labels + spans for offline demo/CI
├── docs/                         # DESIGN.md, CASE-STUDY.md, diagrams/ (placed by Mir)
├── .github/
│   ├── workflows/ci.yml          # R11: schema + opa test + eval + coverage
│   └── CODEOWNERS                # R9: four-eyes
├── Makefile                      # make demo, make report, make test
├── config/                       # profiles: oss (default), hybrid; feature flags
└── requirements.md / design.md / tasks.md
```

**Language/runtime.** Python service for the Guard, API, eval, review, and report tooling (per steering stack). OPA/Rego for policy. YAML + JSON Schema for the register. GitHub Actions for CI.

---

## 3. Data model

Four records (DESIGN.md §5). Three are versioned in Git; evidence is emitted at runtime.

### 3.1 Requirement (`requirements/*.yaml`)
Fields: `id`, `source` ∈ {EU AI Act, ISO/IEC 27001:2022}, `citation`, `title` (own words), `mode` ∈ {auto, human, hybrid}, `owner`, `status` ∈ {active, draft, retired}, `elements?`, `rule_ref?`.
Invariant: `rule_ref` present ⇒ `mode` ∈ {auto, hybrid} **and** an approved interpretation exists (enforced by a schema + cross-file validator, R1.5).

### 3.2 Interpretation (`interpretations/*.yaml`)
Fields: `id`, `version`, `requirement_id` (FK), `decision` ∈ {confirmed_prohibited_pattern, not_in_scope, needs_review}, `owner`, `reason`, `effective_from`, `review_by`, `rule_ref?`, `eval_cases?`, `status` ∈ {draft, approved}.
Invariants: approved interpretations are immutable (change = new `version`); a hard `deny` requires an approved `confirmed_prohibited_pattern` present in signed policy data (R2.4).

### 3.3 Rule (`policy/`)
Rego + signed data. `data.thresholds[concept_id] = {low, high}`, `data.confirmed_prohibited_patterns = [pattern_id,...]`. Mutable only by PR + four-eyes. Decision shape per DESIGN.md §5.3:
`deny` (pattern_id in confirmed) → `four-eyes` (concept high conf + enough elements) → `ask` (concept present at low conf) → `allow`. Strictest matching outcome wins.

### 3.4 Evidence (OTel span, decision-record v1)
Fields per DESIGN.md §5.4: `ts`, `decision_id`, `bundle_revision`, `pep=semantic`, `subject_pseudonym`, `groups`, `site`, `resource`, `action`, `tier`, `allowed`, `reason_code`, `labels[]`, `args` (key names + count + SHA-256 only), `latency_ms`, `approver_pseudonyms[]`. No clear `agent.id`/role/department; no raw prompt body by default.

### 3.5 Label (Guard output)
`{concept_id, pattern_id?, elements_met[], confidence (0..1), evidence_refs[], detector_versions{stage: version}}`. Never a verdict (R3.2).

---

## 4. Semantic Guard pipeline

Stages run in the `oss` profile without cloud. Stages 2–3 are hybrid-only, off by default.

| Stage | Role | oss | hybrid |
|---|---|---|---|
| 0 | Deterministic signals (PII/secret detectors, data-class tags, schema patterns) | local rules + optional vendored PII detector | same |
| 1 | Embedding similarity vs curated exemplars (incl. hard negatives), DE + EN | local CPU embedding model, in-repo index | same, always on |
| 2 | Vendor/injection classifier | off | Prompt Shields adapter (one signal, not a legal verdict) |
| 3 | LLM judge, pinned rubric, structured JSON → labels | off / local stub | Azure OpenAI or Foundry if access exists |
| A | Artefact/diff analysis: person-ID join + aggregated score + adverse action | local static checks | same |
| S | Session context: rolling, TTL-bounded, pseudonymised **labels only** | in-memory | same |

**Deterministic fallback.** If stages 1–3 are unavailable, stage 0 + any confirmed-pattern match still run. The Guard still returns labels; OPA still decides.

**Why rubric + exemplars, not keywords.** A social-scoring workflow can satisfy every Art. 5(1)(c) element without the phrase, while "fraud risk score" is usually lawful. Detection scores against the legal-element rubric and curated exemplars, so keywords are features, not the decision basis (R3.5).

---

## 5. Adapter interface and profiles

One protocol: `detect(event) -> labels[]`. Backends: `local_embeddings` (required), `prompt_shields` (optional), `lakera` (stub), `aws_placeholder` (unused, reserved slot). Selection is by `config/` profile + feature flags.

- **`oss` (default, CI-guaranteed):** `local_embeddings` + stage 0; judge off; identity via Keycloak/fixture token; OTel → file export. All optional adapters absent must pass CI (R4.3).
- **`hybrid` (optional):** adds `prompt_shields` and optionally the judge adapter; Entra ID groups adapter; same OTel contract. Degrades cleanly when credentials are missing (R4.4). Requires a documented budget alert before enabling (R15.3).

Vendor-adapter scores are reported **separately** from the local path in eval output (R4.5, R12.5). Prompt Shields is documented as detecting jailbreak/injection, not legal-element fit (R4.6).

**Hybrid adapters (Phase 10, implemented).** All sit behind the `detect(event) -> labels[]` protocol, read config from environment variables only (no repo secrets), and share a small stdlib `urllib` transport (`guard/adapters/http_transport.py`) with a typed error model (timeout / 401·403 auth / 429 rate-limit / 5xx). On no credentials they report `available() is False` and are skipped; on a live failure they raise, so the Guard marks them failed and the pipeline applies the fail-safe tier (never a silent allow).
- `prompt_shields` (`guard/adapters/prompt_shields.py`): Azure AI Content Safety. Emits a label under the **separate** concept `PROMPT-INJECTION`, so OPA (which only knows legal concepts) never treats it as an Art. 5 finding and it is scored separately.
- `judge` (`guard/adapters/judge.py`): stage-3 Azure OpenAI / Foundry, **off by default** (`judge_enabled`), pinned deployment + pinned `RUBRIC`, structured-JSON → labels, with a `StubJudge` for offline tests and clean fallback to stages 0-1 when unavailable.
- `lakera` / `aws_placeholder` (`guard/adapters/stubs.py`): protocol-conformant, inert (always `[]`).
- Identity (`identity/provider.py`): `FixtureIdentityProvider` (default, Keycloak/fixture token) and optional `EntraIdentityProvider` that normalises group claims and degrades to fixture when its env config is absent.
The hybrid eval (`eval/hybrid_runner.py`, `make hybrid-eval`) scores the vendor path separately and renders `TO BE MEASURED` until a real credentialed run exists. Runbook: `docs/HYBRID.md`.

---

## 6. OPA policy

`policy/tier.rego` consumes `input.labels`, `data.thresholds`, `data.confirmed_prohibited_patterns` and returns a single `tier`. `deny` is reachable only via a confirmed pattern, which only exists via an approved `confirmed_prohibited_pattern` interpretation merged through four-eyes. Thresholds/patterns are signed data, never mutated at runtime (R6.4). `policy/tier_test.rego` covers deny / four-eyes / ask / allow and runs under `opa test` in CI (R6.5).

---

## 7. HTTP API, fixture mode, fail-safe

**`POST /v1/labels`** (versioned path). Request: tool metadata + session-label summary + in-memory classification text. Response: `labels[]` per §3.5. No raw bodies persisted by default (R7.4).

**Fixture mode** (`config` flag): returns committed labels/spans from `fixtures/`; no live gateway, no cloud call. Used by `make demo` and CI (R7.3).

**Fail-safe (R8):** Guard timeout or 5xx ⇒ deterministic gateway path unaffected; tools in the `risky` class forced to `ask`; never a silent `allow`. `log-only` classes may fail open; the class→behaviour table is documented. Tests cover adapter-absent, timeout, and 5xx with assertions that no silent allow occurs.

---

## 8. Four-eyes review and feedback loop

`review/` provides a recorder: given an `ask`/`four-eyes` outcome it captures `owner`, `reason`, `decision`, then writes (or updates) a branch/PR adding an interpretation YAML + eval-case fixtures in one change set. No runtime writes to policy, interpretations, confirmed patterns, or thresholds (R9.3). `.github/CODEOWNERS` enforces two distinct approvers. Replaying the same prompt after a simulated merge follows the new rule (R9.5).

---

## 9. Evidence, CI, eval, reports

**Evidence (R10).** `guard/evidence/` emits one span per decision carrying the decision-record v1 fields, a pseudonymised (salted) subject and approvers, args reduced to names/count/SHA-256 only, and no clear identity or raw body (a build-time check rejects forbidden fields). The record is OTel-shaped (span name + flat attribute map) so it maps directly onto a real OpenTelemetry span when the SDK is present; the `oss` default is a JSONL **file exporter** (one span per line), a demo/CI sink and hand-off point — this repo is not the long-term store. `aca.pipeline.DecisionPipeline` ties Guard labels → OPA decision → one span; a Guard outage records the fail-safe tier (risky/unknown → `ask`), never a silent allow, using the Guard's `label_with_health` signal to tell "ran clean" from "Guard down".

**CI (R11)** `.github/workflows/ci.yml`: (1) JSON Schema validation of requirements + interpretations incl. cross-file invariants; (2) `opa test`; (3) eval set (attack/benign/ambiguous, DE+EN); (4) coverage report (`% mapped` / `% auto` / `% human` / `% hybrid`), failing below the configured floor (floor is a TARGET). All pass on `oss` with optional adapters absent.

**Eval (R12).** `eval/` runner measures precision/recall per language, benign false-block rate, and semantic-path p95 (stages 0–1 and 2–3 separately), persisting results with timestamp + git SHA. Includes hard negatives and at least one multi-turn "salami" case. Until a committed run exists, metrics render as `TARGET` / `TO BE MEASURED`.

**Report (R13).** `make report` builds a PDF (map, coverage, latest committed eval results or "not measured", decision-log excerpt from fixture spans) and **fails closed** if a required field is missing. Carries disclaimers.

---

## 10. Identity and Azure

No cloud IdP required. Tests use Keycloak or a fixture token; Entra ID is an optional adapter (R15.1). Docs record the verified lab account facts and the open TODOs (DESIGN.md §15). A budget alert is a documented prerequisite before any `hybrid` adapter is enabled; unverified Prompt Shields / Azure OpenAI / Foundry limits are never assumed (R15.2, R15.3).

---

## 11. Threat and safety notes

- **Silent allow on Guard failure** → fail-safe to `ask` for risky classes; tested (R8).
- **Self-modifying policy** → all policy/interpretation changes are PR + four-eyes; no runtime writes (R9.3).
- **Over-trusting a vendor signal** → Prompt Shields/judge are signals, not verdicts; scored separately; OPA decides (R4.5, R4.6, R5).
- **PII leakage in evidence** → pseudonymised subject, no clear identity, args hashed, no raw bodies by default (R10).
- **Invented metrics** → every number requires a committed run with provenance; else TARGET (R12).
- **Over-claiming compliance** → disclaimers across README/report/docs; illustrative mapping only (R16.4).
- **Prompt injection via classified text** → classification text handled in memory, not persisted; treated as data, not instructions.
- **Boundary violations** → no edits to `src/apm_cli/**`, no PR to `microsoft/apm`, no change to `agent-trust-gateway`, no sibling-repo implementation (R16.3).

---

## 12. Testing strategy

Required test coverage (steering): JSON Schema validation (incl. invalid enums, missing fields, broken FK, `rule_ref` invariant), Rego (`opa test` all four tiers), Guard adapters **including adapter-absent paths**, fail-safe (timeout/5xx/risky→ask), and the eval runner. Judge path testable via the local stub. `oss` profile is the CI gate.

---

## 13. Build order (summary; detail in `tasks.md`)

`oss` first: schemas + register → Rego + tests → Guard stages 0–1 + label schema → artefact/session stages → API + fixture mode → fail-safe → evidence spans → review/four-eyes → eval runner → coverage → report → demo. Then optional hybrid adapters (Prompt Shields, judge, Entra) behind flags, each degrading cleanly.

## 14. Open questions / deferred

- Exact embedding model and whether to vendor a PII detector (licence check) — decided at implementation.
- Coverage floor value — set once the starter map is encoded (TARGET).
- Hybrid adapter enablement gated on the DESIGN.md §15 TODOs (budget alert, Prompt Shields/OpenAI/Foundry access, Entra group claims).
- Second-cloud (AWS) adapter slot stays reserved and unimplemented.

## 15. Traceability

R1/R2 → §2, §3; R3 → §4, §3.5; R4 → §5; R5 → §4, §5; R6 → §3.3, §6; R7 → §7; R8 → §7, §11; R9 → §8; R10 → §3.4, §9; R11 → §9; R12 → §9; R13 → §9; R14 → §13, demo; R15 → §10; R16 → §1, §11.
