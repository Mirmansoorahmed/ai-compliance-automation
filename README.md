# AI Compliance Automation

**Core component: Semantic Guard** — it emits contextual intent *labels* and confidence for prompts, tool calls, and code artefacts. **OPA decides** `allow` / `ask` / `four-eyes` / `deny`. A GitHub-native harness that turns a legal or ISMS requirement into a versioned human interpretation, then an OPA rule, then evidence.

> Lab / portfolio project. **Synthetic data only** (fictional consultancy *Northwind Advisory*, fictional client *NordPay*). Mappings to the EU AI Act and ISO/IEC 27001:2022 are **illustrative** and in our own words — not legal advice, not a conformity claim. Part of the AI Governance Platform.

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

Metrics come only from a committed eval run (timestamp + git SHA). Where no run exists, a cell reads `TO BE MEASURED`.

| Metric | de | en |
|---|---|---|
| Label precision | 1.0 | 1.0 |
| Label recall | 1.0 | 1.0 |
| Benign false-block rate | 0.0 | 0.0 |
| Semantic path p95 (stages 0-1, ms) | 1.983 | 1.983 |
| Semantic path p95 (stages 2-3, ms) | TO BE MEASURED | TO BE MEASURED |

_Source: committed eval run 2026-11-14 18:11 UTC, git `7432bf55`, embedder `hashed/0.1.0:dim=256` (see [`eval/results/`](eval/results/))._

> **Read these as a baseline, not a quality claim.** This committed run uses the deterministic **hashed-vector embedding fallback** (so CI is reproducible offline), not a trained model. On a tiny curated set it separates positives from hard negatives cleanly; it is not evidence of real-world detector accuracy. Re-measure with the MiniLM-class model and a larger set before citing any number elsewhere.

## Limitations

- Lab and synthetic data; mappings are illustrative; no conformity claim and no automation of indeterminate legal concepts.
- Committed metrics use the hashed fallback embedder (see note above); stages 2–3 and vendor paths are not measured on `oss`.
- Azure for Students credit/expiry are known, but Prompt Shields / Azure OpenAI / Entra limits are unverified — a budget alert is a prerequisite before any hybrid call ([`docs/DESIGN.md` §15](docs/DESIGN.md)).
- This repo does not implement the sibling projects (audit logging, red-teaming, multi-agent) and does not change the gateway.

## License

See [`LICENSE`](LICENSE).
