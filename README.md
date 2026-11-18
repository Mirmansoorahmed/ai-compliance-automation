# AI Compliance Automation

**Core component: Semantic Guard** — it emits contextual intent *labels* and confidence for prompts, tool calls, and code artefacts. **OPA decides** `allow` / `ask` / `four-eyes` / `deny`. A GitHub-native harness that turns a legal or ISMS requirement into a versioned human interpretation, then an OPA rule, then evidence.

> Lab / portfolio project. **Synthetic data only** (fictional consultancy *Northwind Advisory*, fictional client *Halvaro Payments GmbH*). Mappings to the EU AI Act and ISO/IEC 27001:2022 are **illustrative** and in our own words — not legal advice, not a conformity claim. Part of the AI Governance Platform.

## Problem

A deterministic gateway can decide *who* may call *which* tool. It cannot tell whether a request is, in effect, building something the law prohibits — e.g. a social-scoring workflow typed into a coding agent without ever saying "social scoring". Indeterminate legal concepts cannot be fully automated. So: a machine flags elements, a **named human interprets** the hard cases, and only an already-interpreted reading is enforced automatically. Each human decision becomes a versioned interpretation plus eval cases via a pull request — the system never rewrites its own policy.

## Architecture

![Architecture — AI Compliance Automation and its core Semantic Guard on the slow path, with the existing gateway as the PEP](docs/diagrams/architecture.png)

The existing gateway stays the PEP. On the slow path it calls the **Semantic Guard** (`POST /v1/labels`). The Guard labels the request (stages 0–1 local; 2–3 optional cloud). OPA maps labels + signed data to a tier. Ambiguous cases go to four-eyes review, which records an interpretation + eval cases through a PR. One OpenTelemetry-shaped span per decision carries pseudonymised evidence. Full design: [`docs/DESIGN.md`](docs/DESIGN.md); the engineering design and data model: [`design.md`](design.md); the four-eyes loop: [`docs/FOUR-EYES.md`](docs/FOUR-EYES.md).

## Semantic Guard (core)

- **Labels, not verdicts.** `{concept_id, pattern_id?, elements_met[], confidence, evidence_refs[], detector_versions{}}`. OPA is the only decision point.
- **Rubric + exemplars, not keywords.** Detection scores against legal-element rubrics and curated DE/EN exemplars (positives and hard negatives), so "compute a fraud risk score" (lawful) stays low while a keyword-free joined-behaviour ranking with an adverse action scores high.
- **Stages:** 0 deterministic signals · 1 local embedding similarity · A artefact/diff analysis · S session context (labels only). Stages 2 (Prompt Shields) and 3 (LLM judge) are optional hybrid adapters, off by default.
- **Fail-safe.** If the Guard is down, risky tools degrade to `ask` — never a silent allow.

## How to run

The default `oss` profile runs fully offline on the Python standard library — no cloud account, no third-party install needed.

```bash
make demo      # the 3 scenarios below (oss profile, offline, < 15 min)
make report    # build the evidence-pack PDF (fails closed on missing fields)
make test      # pytest suite
make schema    # validate the requirement/interpretation register
make opa-test  # run `opa test` on the Rego (needs the opa binary)
make eval      # run the eval set; writes a provenanced results file
make coverage  # requirement coverage report
```

Demo scenarios (DESIGN.md §12): **1)** a keyword-free social-scoring prompt → `deny`; **2)** an ambiguous request → `ask`/four-eyes → a recorded interpretation + eval cases → replay after merge follows the new rule; **3)** a benign "fraud risk score" hard negative → `allow`. The same scenarios run under the `hybrid` profile when Azure credentials exist.

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
- Committed metrics use the hashed fallback embedder (see note above); stages 2–3 and vendor paths are not measured on `oss`.
- A low-cost Azure lab subscription with a budget alert gates the hybrid profile, but Prompt Shields / Azure OpenAI / Entra limits are unverified — a budget alert is a prerequisite before any hybrid call ([`docs/DESIGN.md` §15](docs/DESIGN.md)).
- This repo does not implement the sibling projects (audit logging, red-teaming, multi-agent) and does not change the gateway.

## License

See [`LICENSE`](LICENSE).
