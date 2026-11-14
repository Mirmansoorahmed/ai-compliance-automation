# Tasks — AI Compliance Automation

Ordered implementation plan. **`oss` profile first** (Semantic Guard local path), then optional hybrid adapters. Prefer small, testable slices. Every task lists a test hook and the requirements it satisfies.

**Do not start coding until Mir approves this spec.**

Legend: each task ⇒ `[Rn]` traces to `requirements.md`. "Test hook" = the automated check that proves the slice.

---

## Phase 0 — Repo scaffold and CI skeleton

- [ ] 0.1 Create the directory layout from `design.md` §2 and a `Makefile` with stub targets `test`, `demo`, `report`. **[R16]**
  - Test hook: `make test` runs and reports "no tests yet" without error.
- [ ] 0.2 Add `config/` profiles (`oss` default, `hybrid`) and a feature-flag loader; default to `oss`. **[R4.2]**
  - Test hook: unit test asserts default profile is `oss` and unknown flags are rejected.
- [ ] 0.3 Add `.github/workflows/ci.yml` skeleton (jobs: schema, opa-test, eval, coverage) wired to run on PR, initially allowed to be empty-pass. **[R11.1]**
  - Test hook: CI runs green on an empty register.

## Phase 1 — Register and schema (oss)

- [ ] 1.1 Author JSON Schemas for requirement and interpretation (`schemas/`). **[R1.2, R2.2]**
  - Test hook: schema unit tests accept valid docs, reject missing fields and bad enums.
- [ ] 1.2 Implement a validator with cross-file invariants: `requirement_id` FK, `rule_ref` ⇒ `mode`∈{auto,hybrid}+approved interpretation, approved interpretation immutability, `eval_cases` paths exist. **[R1.5, R2.2, R2.3, R2.5]**
  - Test hook: validator tests cover each invariant (pass + each failure).
- [ ] 1.3 Encode the v1 starter map (11 requirements, DESIGN.md §6) with own-words titles. **[R1.1, R1.3, R1.4]**
  - Test hook: all requirement files validate; a test asserts the 11 IDs and their modes.
- [ ] 1.4 Wire schema + validator into the CI `schema` job. **[R11.1]**
  - Test hook: CI fails on an intentionally broken fixture, passes on the real set.

## Phase 2 — OPA policy (oss)

- [ ] 2.1 Implement `policy/tier.rego` (DESIGN.md §5.3 shape) consuming `input.labels`, `data.thresholds`, `data.confirmed_prohibited_patterns`. **[R6.1, R6.2, R6.3]**
- [ ] 2.2 Add signed data files (`thresholds.json`, `confirmed_prohibited_patterns.json`); document "PR + four-eyes only, no runtime mutation". **[R6.4]**
- [ ] 2.3 Write `policy/tier_test.rego` covering deny / four-eyes / ask / allow. **[R6.5]**
  - Test hook: `opa test` passes all four outcomes in the CI `opa-test` job.

## Phase 3 — Label schema and Guard stages 0–1 (oss core)

- [ ] 3.1 Define the label schema + `detector_versions` (`guard/labels/`). **[R3.1, R3.8]**
  - Test hook: schema test; a Guard output never carries a verdict field.
- [ ] 3.2 Implement stage 0 deterministic signals (PII/secret, data-class tags, schema patterns). **[R3.3]**
  - Test hook: unit tests on synthetic inputs produce expected signals.
- [ ] 3.3 Curate DE+EN exemplars for Art. 5(1)(c) (positives + hard negatives) under `exemplars/`. **[R3.4]**
  - Test hook: exemplar loader test; counts/ids asserted; hard negatives present.
- [ ] 3.4 Implement stage 1 local embedding similarity + in-repo index; rubric-based scoring, not keyword decision. **[R3.3, R3.5]**
  - Test hook: positives score above negatives on the exemplar set (deterministic seed).
- [ ] 3.5 Implement the `local_embeddings` adapter behind `detect(event)->labels[]`. **[R3.1, R4.1]**
  - Test hook: adapter returns schema-valid labels; verdict never present.

## Phase 4 — Artefact and session stages (oss)

- [ ] 4.1 Implement stage A artefact/diff analysis: person-ID join + aggregated score + adverse action. **[R3.6]**
  - Test hook: synthetic diff fixtures flag all three elements; benign diff does not.
- [ ] 4.2 Implement stage S session context: rolling, TTL-bounded, pseudonymised labels only. **[R3.7]**
  - Test hook: test asserts no raw prompt text stored; TTL expiry works.

## Phase 5 — API, fixture mode, fail-safe (oss)

- [ ] 5.1 Implement `POST /v1/labels` returning the label schema; no raw bodies persisted. **[R7.1, R7.2, R7.4]**
  - Test hook: API contract test (request/response); no persistence of bodies.
- [ ] 5.2 Implement fixture mode returning committed labels/spans from `fixtures/`. **[R7.3]**
  - Test hook: fixture-mode test runs with no network.
- [ ] 5.3 Implement fail-safe: risky-class table, timeout/5xx handling, never silent allow; document fail-open vs fail-safe classes. **[R8.1, R8.2, R8.3]**
  - Test hook: tests for adapter-absent, timeout, and 5xx assert risky→`ask`, no silent allow. **[R8.4]**

## Phase 6 — Evidence spans (oss)

- [x] 6.1 Implement OTel span emitter with decision-record v1 fields; pseudonymised subject; args as key/count/SHA-256; file exporter. **[R10.1, R10.2, R10.3, R10.4]**
  - Test hook: span test asserts required fields present and no clear identity / raw body.
  - Done: `guard/evidence/` (redact, record, emitter) + `aca.pipeline.DecisionPipeline` wiring Guard→OPA→span; file (JSONL) exporter, optional OTel bridge. Fail-safe records `ask` on Guard outage (no silent allow).

## Phase 7 — Four-eyes review and feedback (oss)

- [ ] 7.1 Implement the review recorder (`owner`, `reason`, `decision`) that writes/updates a PR adding interpretation YAML + eval cases; no runtime policy writes. **[R9.1, R9.2, R9.3]**
  - Test hook: test produces a diff (interpretation + fixtures) and asserts no policy mutation at runtime.
- [ ] 7.2 Add `.github/CODEOWNERS` for four-eyes; document the two-distinct-approver gate. **[R9.4]**
  - Test hook: replay test — same prompt after simulated merge follows the new rule. **[R9.5]**

## Phase 8 — Eval runner, coverage, metrics discipline (oss)

- [ ] 8.1 Build the labelled eval set (attack/benign/ambiguous, DE+EN), including hard negatives and ≥1 multi-turn "salami" case. **[R11.2, R12.4]**
  - Test hook: eval set loads; category + language coverage asserted.
- [ ] 8.2 Implement the eval runner: precision/recall per language, benign false-block rate, semantic-path p95 (0–1 and 2–3 separately); persist results with timestamp + git SHA. **[R12.1, R12.2, R12.5]**
  - Test hook: runner writes a results file with provenance; vendor path scored separately.
- [ ] 8.3 Implement the coverage report (`% mapped` / `% auto` / `% human` / `% hybrid`) with a configurable floor (TARGET). **[R11.3, R11.4]**
  - Test hook: coverage job fails below floor on a broken fixture, passes on the real set.
- [ ] 8.4 Ensure TARGET / TO BE MEASURED rendering wherever no committed run exists. **[R12.3]**
  - Test hook: doc/report test asserts no hard-coded metric without provenance.
- [ ] 8.5 Confirm all CI jobs pass on `oss` with optional adapters absent. **[R11.5]**
  - Test hook: CI green with hybrid flags off.

## Phase 9 — Report and demo (oss)

- [ ] 9.1 Implement `make report` → PDF (map, coverage, latest committed eval or "not measured", decision-log excerpt); fail closed on missing required field; include disclaimers. **[R13.1, R13.2, R13.3]**
  - Test hook: report test produces a PDF on complete data and errors (no PDF) on missing field.
- [ ] 9.2 Implement `make demo` for the three DESIGN.md §12 scenarios on `oss`, under 15 minutes, offline. **[R14.1, R14.2, R14.3, R14.4]**
  - Test hook: a smoke test runs all three scenarios in fixture mode and asserts deny/four-eyes/allow outcomes.
- [ ] 9.3 Write the README (≤3-minute skim): problem → diagram → Semantic Guard → how to run → results table (when measured) → limitations; name Semantic Guard as core; disclaimers; no branding. **[R16.1, R16.2, R16.4]**
  - Test hook: README lint/structure check (sections present, Semantic Guard named, disclaimer present).

## Phase 10 — Optional hybrid adapters (feature-flagged, degrade cleanly)

- [ ] 10.1 Document Azure prerequisites and the budget-alert gate (DESIGN.md §15); do not enable paid adapters without it. **[R15.2, R15.3]**
  - Test hook: docs test asserts prerequisite text present; default config keeps hybrid off.
- [ ] 10.2 Implement the `prompt_shields` adapter (one signal, not a verdict); scored separately; degrades cleanly when creds absent. **[R4.1, R4.4, R4.5, R4.6]**
  - Test hook: adapter-absent + adapter-present (mocked) tests; oss CI unaffected.
- [ ] 10.3 Implement the stage-3 judge adapter (Azure OpenAI / Foundry), off by default, pinned model + rubric, structured-JSON parser, local stub for tests, fallback to stages 0–1. **[R5.1, R5.2, R5.3, R5.4]**
  - Test hook: stub-judge test; fallback test when judge unavailable.
- [ ] 10.4 Add `lakera` stub and `aws_placeholder` unused slot conforming to the adapter protocol. **[R4.1]**
  - Test hook: protocol-conformance test; both selectable but inert.
- [ ] 10.5 Implement the Entra ID groups adapter (optional); Keycloak/fixture token remains default. **[R15.1]**
  - Test hook: identity test passes with fixture token; Entra path mocked.
- [ ] 10.6 Run the three demo scenarios under `hybrid` when credentials exist; vendor scores reported separately. **[R14.5, R12.5]**
  - Test hook: hybrid demo smoke test (mocked creds) mirrors oss outcomes.

---

## Done criteria for this spec turn

`requirements.md`, `design.md`, and `tasks.md` exist on branch `spec`. **Stop for review.** No implementation code in this turn.
