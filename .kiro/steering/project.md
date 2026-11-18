# Steering — ai-compliance-automation

## Purpose
Portfolio project under the **AI Governance Platform** umbrella. **AI Compliance Automation** (`ai-compliance-automation`) is a GitHub-native harness that maps legal and ISMS requirements to versioned human interpretations, then to OPA rules and evidence.

**Core component: Semantic Guard.** It emits contextual intent *labels* only; OPA decides allow / ask / deny. This is the semantic / contextual slow path next to the deterministic gateway.

Demo consultancy: **Northwind Advisory**. Demo client: **Halvaro Payments GmbH** (fictional Berlin fintech, ~2,000 employees, several sites).

## Sibling and boundaries
- The Agent Access Governance Gateway already exists and stays the PEP. This repo is a standalone sibling. Integrate through a versioned HTTP label API (Semantic Guard) and a shared decision-record / OTel contract. Provide a recorded fixture mode so demos run without a live gateway.
- Do not edit `src/apm_cli/**`, do not open a PR to microsoft/apm, and do not change `agent-trust-gateway`.
- Do not build **AI Audit Logging & Monitoring** (`ai-audit-logging`) or the **LLM Red-Teaming Pipeline** (`llm-red-teaming-pipeline`) here. Emit spans and eval cases those siblings can consume later. The **Multi-Agent AI System (LangGraph)** (`langgraph-multi-agent-system`) is a later project, out of scope for this repo.

## Stack (hybrid, portable by default)
- **Default profile `oss` (CI must pass with this only):** Python service, OPA/Rego, local embeddings plus deterministic stage-0 signals (Semantic Guard core), Keycloak when identity is needed, OpenTelemetry, optional self-hosted Langfuse, YAML + JSON Schema in Git, PDF report.
- **Optional profile `hybrid`:** same core, plus feature-flagged adapters for Entra ID (groups), Azure AI Content Safety Prompt Shields (one Guard signal, not a legal verdict), and optionally Azure OpenAI or Azure AI Foundry as a pinned judge. These must degrade cleanly when credentials are missing.
- Reserve an unused adapter slot for a possible second cloud (maybe AWS; unconfirmed). Do not design the system around it.
- Azure lab account, **verified in the portal on 14 November 2026 (Europe/Berlin):** Azure for Students, USD $90 credit, expires 7 November 2027, IU tenant. Prompt Shields, Azure OpenAI / Foundry access, Entra group-claim limits, region and quota are still unverified — see DESIGN.md §15. **Set a budget alert** before any hybrid-profile calls. Do not assume those unverified limits.

## Hard constraints
- **Synthetic data only.** Fictional firms: Northwind Advisory and NordPay. No real client data. Default NordPay size in this project is ~2,000 employees; do not edit older NordPay repos from here.
- **No employer branding** on demos, READMEs, or reports.
- **No AI attribution** and **no `Co-authored-by`** (or similar) on commits.
- **Never invent metrics.** Every number in README / report / case study must come from a **committed eval run** with **timestamp + git SHA**. Until then write "TO BE MEASURED" or "TARGET".
- **Do not copy legal or standard text.** Article and Annex A IDs plus short titles in our own words only. Mappings are illustrative, not a conformity claim.
- **No self-modifying policy.** Interpretations and eval cases enter through a PR with four-eyes review.
- Tests required for schema validation, Rego, Semantic Guard adapters (including "adapter absent" paths), fail-safe behaviour, and the eval runner.
- README must be skimmable in ~3 minutes: problem → diagram → Semantic Guard → how to run (`make demo`, both profiles) → results table (when measured) → limitations.

## Docs Mir will place for you
- `docs/DESIGN.md` (product design)
- `docs/CASE-STUDY.md` (consulting narrative; do not invent results)
- `docs/diagrams/architecture.png` (and the `.mmd` source)
- `README.md` (title area must name Semantic Guard as the core component)

## Out of scope (v1)
- Production HA, multi-region cut-over, or a second-cloud implementation
- A full ISO/IEC 42001 Annex A mapping
- Treating an LLM judge or Prompt Shields as an authorization control
- Implementing `llm-red-teaming-pipeline`, `ai-audit-logging`, or `langgraph-multi-agent-system`
