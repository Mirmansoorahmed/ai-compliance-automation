# Compliance Check Catalog — ai-coding-compliance-guardrails-eu (v2 design)

> Northwind Advisory for Halvaro Payments GmbH (fictional client, Berlin fintech). Design document, v2. Synthetic examples only. Legal text is paraphrased in our own words; this is not legal advice and not a conformity claim. Indeterminate legal concepts stay with a named human reviewer.

> The machine-readable form of this catalog is [`../../policy/catalog/catalog.yaml`](../../policy/catalog/catalog.yaml) (policy data, the single source of truth). This markdown is the human-readable companion.

Status of the law used here: Regulation (EU) 2024/1689 (AI Act) **as amended by Regulation (EU) 2026/1744 (AI Omnibus, in force 27 July 2026)**, Regulation (EU) 2016/679 (GDPR), ISO/IEC 42001:2023 (control themes from public summaries, paraphrased), OWASP Top 10 for LLM Applications 2025 and OWASP Top 10 for Agentic Applications 2026. Checked 18 Nov 2026.

## 1. What this catalog is

Every row is one check the harness can run while a developer builds software with an AI coding tool (Claude Code, Cursor, GitHub Copilot, Codex, Kiro, or any MCP client). A check has a plain-language trigger, a sample developer prompt in English and German, a decision, the artefacts that must exist before the code can ship, which part is deterministic and which part is semantic, and where it is enforced.

### Decisions

| Decision | What the developer sees | What happens next |
|---|---|---|
| **BLOCK** | The coding agent refuses and explains which rule applies. | CI fails and the deploy gate denies. The only override is a documented legal exception, approved by two people (four-eyes). |
| **ASK** | The agent pauses: "This needs a human decision." | A reviewer decides. The decision becomes a versioned interpretation plus new eval cases through a pull request. |
| **WARN** | The agent continues, but shows the obligations (for example, "high-risk under Annex III 4(a)"). | The obligations are written into `use-case.yaml`. CI shows them as pending. The **deploy gate blocks** until the artefacts exist and are approved. |
| **ALLOW** | Nothing visible. | The decision is logged as evidence. ISO 42001 rows are evidence checks: they never stop a developer; the deploy gate only checks that the record exists for high-risk use cases. |

### Enforcement points

| Code | Where | Examples |
|---|---|---|
| IDE | Prompt hook, before the model sees the request | Claude Code `UserPromptSubmit`, Cursor `beforeSubmitPrompt`, Kiro Prompt Submit, Codex `UserPromptSubmit` |
| AGT | Agent tool or file hook, before a tool runs or a file is written | `PreToolUse` (Claude Code, Codex, Kiro), Cursor `preToolUse`/`beforeShellExecution`/`beforeMCPExecution`, Copilot `preToolUse` |
| CI | Pull-request checks | GitHub Action running the policy service, Semgrep, gitleaks, schema checks; required status check |
| DEP | Deploy gate | GitHub environment protection rule, Kubernetes admission (OPA Gatekeeper), Azure Pipelines check |
| RT | Runtime | Agent Trust Gateway (MCP / tool calls), application-side checks |
| ORG | Organisational process | Evidence is collected; no automatic decision |

### Status labels

- **ACA: implemented** — exists today in the current repo (formerly ai-compliance-automation) and is covered by its eval.
- **ACA: partial** — a requirement, threshold, adapter or evidence path exists, but not the full check.
- **Gateway (linked)** — enforced by the separate Agent Trust Gateway repo, which is linked, never modified.
- **New** — to be built (see ARCHITECTURE.md, build plan).

## 2. Size of the catalog

| Source | Checks |
|---|---|
| EU AI Act (incl. Omnibus changes) | 57 |
| GDPR / DSGVO | 15 |
| German national add-ons (BDSG, BetrVG) | 2 |
| ISO/IEC 42001 (clauses 4-10 + Annex A themes) | 18 |
| Security best practice (OWASP LLM 2025, OWASP Agentic 2026, secure SDLC) | 26 |
| DORA (fintech add-on) | 2 |
| **Total** | **120** |

| Decision | Count |
|---|---|
| BLOCK | 20 |
| ASK | 24 |
| WARN | 56 |
| ALLOW | 20 |

| Status | Count |
|---|---|
| ACA: implemented | 2 |
| ACA: partial | 13 |
| Gateway (linked) | 4 |
| New | 101 |

The Appendix maps all 38 ISO/IEC 42001 Annex A controls to the harness evidence that supports them.

## 3. Dates that matter (verified on EUR-Lex)

| What | Applies from | Source |
|---|---|---|
| Art. 5 prohibitions (a)-(h), definitions, AI literacy | 2 Feb 2025 | Art. 113(a) |
| GPAI model obligations (Art. 53, 55) | 2 Aug 2025 | Art. 113(b) |
| Art. 50 transparency; general application | 2 Aug 2026 | Art. 113 |
| Art. 50(2) marking for generative systems already on the market before 2 Aug 2026 | 2 Dec 2026 | Art. 111(4) as amended by 2026/1744 |
| New prohibitions Art. 5(1)(ba) intimate deepfakes, (bb) CSAM | 2 Dec 2026 | Art. 113 as amended by 2026/1744 |
| High-risk rules for Annex III systems (Art. 6(2)) | 2 Dec 2027 | Art. 113 as amended by 2026/1744 |
| High-risk rules for Annex I products (Art. 6(1)) | 2 Aug 2028 | Art. 113 as amended by 2026/1744 |

Design consequence: the harness enforces Art. 5 as BLOCK today. Annex III checks are WARN today with artefacts required at the deploy gate, so Halvaro is ready before 2 Dec 2027. GDPR applies to all of this already.

## 4. The checks

The full 120-row table (with EN/DE example prompts, required artefacts, deterministic vs semantic split, and enforcement points) is maintained in machine-readable form in [`../../policy/catalog/catalog.yaml`](../../policy/catalog/catalog.yaml) and rendered per group there. The groups are:

- **EU AI Act — Scope and triage:** AIA-3-1, AIA-ROLE, AIA-UC-DECL.
- **EU AI Act — Art. 5 prohibited practices (BLOCK):** AIA-5-1-a, -b, -ba, -bb, -c (social scoring, *ACA: implemented*), -d, -e, -f (*ACA: partial*), -g, -h.
- **EU AI Act — Art. 6 classification (ASK):** AIA-6-1, AIA-6-3 (Annex III exception, invalid when the system profiles people).
- **EU AI Act — Annex III high-risk use cases (WARN, some ASK):** AIA-A3-1a/1b/1c, -2, -3a..3d, -4a (CV screening), -4b, -5a, -5b (credit scoring), -5c, -5d, -6a-e, -7a-d, -8a, -8b.
- **EU AI Act — High-risk provider requirements (WARN, become deploy-gate artefacts):** AIA-9, -10, -11, -12, -13, -14, -15, -17, -43-49, -72, -73.
- **EU AI Act — Deployer obligations:** AIA-26-1, -26-7 (worker information), -26-11, -27 (FRIA), -86.
- **EU AI Act — Art. 50 transparency:** AIA-50-1, -50-2, -50-3, -50-4a, -50-4b.
- **EU AI Act — GPAI and AI literacy:** AIA-53, -55, -4.
- **GDPR / DSGVO:** GDPR-5-1b, -5-1c, -5-1e, -6, -9, -10, -13-14, -22 (SCHUFA), -25, -28, -30, -32 (BLOCK), -33-34, -35 (DPIA), -44.
- **German national add-ons:** DE-BDSG-26, DE-BETRVG-87 (works-council co-determination).
- **DORA (fintech add-on):** DORA-28, DORA-17.
- **ISO/IEC 42001 management system (ALLOW / evidence):** ISO42-C4, -C5, -C6-1-2, -C6-1-3, -C6-1-4, -C6-2, -C7, -C9, -C10.
- **ISO/IEC 42001 Annex A themes (ALLOW / evidence):** ISO42-A2..A10.
- **Security — OWASP LLM Top 10 (2025):** SEC-LLM01..LLM10.
- **Security — OWASP Agentic Top 10 (2026):** SEC-ASI01..ASI10 (several *Gateway (linked)*).
- **Security — Secure SDLC and supply chain:** SEC-SECRETS (BLOCK), SEC-SAST, SEC-SCA-SBOM, SEC-IAC-REGION (BLOCK), SEC-SHADOW-AI, SEC-PROVENANCE (BLOCK).

Each row in `catalog.yaml` carries: `law`, `grp`, `id`, `src` (legal source, our own words), `url`, `title`, `trigger`, `en`/`de` example prompts, `dec` (BLOCK/ASK/WARN/ALLOW), `art` (required artefacts), `det` (deterministic signal), `sem` (semantic signal), `ep` (enforcement points), `status`.

## 5. Reading notes and boundaries

- **Fraud detection is not credit scoring.** Annex III 5(b) excludes systems used to detect financial fraud. Transaction-based fraud scoring on objective facts stays ALLOW (it is one of the existing ACA hard negatives). It becomes ASK if it uses personality or nationality (Art. 5(1)(d) boundary) or feeds an adverse decision without a human (GDPR Art. 22).
- **Workplace emotion inference is a BLOCK, customer emotion recognition is a WARN.** Art. 5(1)(f) covers workplace and education only; elsewhere it is Annex III 1(c) plus an Art. 50(3) notice.
- **The Art. 6(3) exception never applies when the system profiles people.** The harness checks the code for per-person scoring before accepting an exception claim.
- **FRIA (Art. 27) applies to Halvaro directly** for credit scoring and life/health insurance pricing (Annex III 5(b), 5(c)), even though Halvaro is a private company. It can build on the DPIA (Art. 27(4)).
- **German employee context.** Any per-employee monitoring needs works council co-determination (§ 87(1) no. 6 BetrVG). § 26 BDSG validity must be checked after CJEU C-34/21; the harness only asks for the legal-basis note, it does not decide.
- **Semantic means meaning, not keywords.** The semantic part is always a label with confidence and legal elements met. OPA makes the decision. A missing or slow Guard degrades risky actions to ASK, never to a silent ALLOW.
- **Honest limit.** The current ACA detector reaches strict recall 0.82 on its 77-case tuning set but only 0.11 strict recall on a 21-case held-out set (real multilingual MiniLM, CPU, committed run 18 Nov 2026). Semantic checks for the new prohibitions will start weaker; deterministic signals and the ASK path carry the load until held-out recall improves.

## Appendix A — ISO/IEC 42001 Annex A controls mapped to harness evidence

Control titles are short names from public summaries ([GAICC](https://gaicc.org/blog/iso-42001-annex-a-controls/), [Vanta](https://www.vanta.com/collection/iso-42001/iso-42001-controls)); objectives are paraphrased. 38 controls in 9 areas.

| Control | Short name | Objective in our words | Harness evidence |
|---|---|---|---|
| A.2.2 | AI policy | Written policy on how AI is built and used | Policy bundle (Rego + catalog) with owner and version |
| A.2.3 | Alignment with other policies | Find where security, privacy and quality policies touch AI | Catalog cross-references to GDPR, ISO 27001, DORA |
| A.2.4 | Review of the AI policy | Review on a schedule and after changes | Policy PR history + review date in bundle manifest |
| A.3.2 | AI roles and responsibilities | Clear owners for AI work | owner / overseer fields in use-case.yaml |
| A.3.3 | Reporting of concerns | Safe way to raise AI concerns | 'Report a concern' link in every BLOCK/ASK message; ticket log |
| A.4.2 | Resource documentation | Know what each AI system depends on | AI-BOM generated in CI |
| A.4.3 | Data resources | Record data used | data-sheet (AIA-10) |
| A.4.4 | Tooling resources | Record tools used to build/run AI | AI-BOM incl. coding agents, MCP servers |
| A.4.5 | System and computing resources | Record infra | IaC inventory |
| A.4.6 | Human resources | Record skills and people | overseer competence + literacy record |
| A.5.2 | Impact assessment process | Defined process for impact assessment | Deploy gate requires DPIA/FRIA/impact record for high-risk |
| A.5.3 | Documentation of impact assessments | Keep results | Evidence store, linked to use-case ID |
| A.5.4 | Impact on individuals and groups | Assess effects on people | FRIA / DPIA content |
| A.5.5 | Societal impacts | Assess wider effects | Impact record section |
| A.6.1.2 | Objectives for responsible development | Set responsible-AI objectives | Catalog + eval targets |
| A.6.1.3 | Responsible design and development processes | Define the dev process | This harness (guides, hooks, CI, deploy gate) |
| A.6.2.2 | Requirements and specification | Specify requirements | use-case.yaml + spec |
| A.6.2.3 | Design and development documentation | Record design | tech-doc / design doc |
| A.6.2.4 | Verification and validation | Test before release | eval report with git SHA |
| A.6.2.5 | Deployment | Plan release, confirm requirements met | Deploy gate decision record |
| A.6.2.6 | Operation and monitoring | Run and monitor | pmm-plan + runtime traces |
| A.6.2.7 | Technical documentation | Provide technical docs | Annex IV tech-doc |
| A.6.2.8 | Event logs | Decide and keep event logs | OTel decision spans (ACA evidence) |
| A.7.2 | Data for development and enhancement | Data management for AI | data-sheet |
| A.7.3 | Acquisition of data | Record how data is obtained | provenance fields |
| A.7.4 | Data quality | Quality requirements and checks | data checks in CI |
| A.7.5 | Data provenance | Where data came from | provenance + AI-BOM |
| A.7.6 | Data preparation | Preparation criteria and methods | data-sheet section |
| A.8.2 | System documentation for users | What users need to know | instructions-for-use / disclosure texts |
| A.8.3 | External reporting | Let others report adverse impacts | public contact in notice |
| A.8.4 | Communication of incidents | Plan incident communication | incident runbook |
| A.8.5 | Information for interested parties | Decide what to report to whom | reporting matrix |
| A.9.2 | Processes for responsible use | How AI is used responsibly | harness messages + policy |
| A.9.3 | Objectives for responsible use | Objectives steering use | catalog decisions |
| A.9.4 | Intended use | Use as intended | declared purpose vs runtime purpose check |
| A.10.2 | Allocating responsibilities | Split duties with partners | role field (provider/deployer) + contracts |
| A.10.3 | Suppliers | Suppliers fit the responsible-AI approach | vendor allowlist + DPA + DORA register |
| A.10.4 | Customers | Consider customer needs | instructions-for-use for clients |

## Appendix B — Sources (opened 18 Nov 2026)

- [Regulation (EU) 2024/1689 (AI Act), EUR-Lex](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng)
- [Regulation (EU) 2026/1744 (AI Omnibus), EUR-Lex](https://eur-lex.europa.eu/eli/reg/2026/1744/oj/eng)
- [AI Act Service Desk, article pages](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-5)
- [Commission guidelines on prohibited AI practices (Feb 2025)](https://digital-strategy.ec.europa.eu/en/library/commission-publishes-guidelines-prohibited-artificial-intelligence-ai-practices-defined-ai-act)
- [Commission guidelines on the AI system definition](https://digital-strategy.ec.europa.eu/en/library/commission-publishes-guidelines-ai-system-definition-facilitate-first-ai-acts-rules-application)
- [Draft Commission guidelines on high-risk classification (19 May 2026)](https://digital-strategy.ec.europa.eu/en/library/draft-commission-guidelines-classification-high-risk-ai-systems)
- [Code of Practice on transparency of AI-generated content (June 2026)](https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content)
- [AI Omnibus enters into force (Commission news)](https://digital-strategy.ec.europa.eu/en/news/ai-omnibus-enters-force)
- [Regulation (EU) 2016/679 (GDPR), EUR-Lex](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng)
- [CJEU C-634/21 (SCHUFA)](https://curia.europa.eu/juris/liste.jsf?num=C-634/21)
- [§ 87 BetrVG](https://www.gesetze-im-internet.de/betrvg/__87.html)
- [§ 26 BDSG](https://www.gesetze-im-internet.de/bdsg_2018/__26.html)
- [Regulation (EU) 2022/2554 (DORA)](https://eur-lex.europa.eu/eli/reg/2022/2554/oj/eng)
- [ISO/IEC 42001 Annex A summary (GAICC)](https://gaicc.org/blog/iso-42001-annex-a-controls/)
- [ISO/IEC 42001 controls overview (Vanta)](https://www.vanta.com/collection/iso-42001/iso-42001-controls)
- [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/llm-top-10/)
- [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/)
- [CycloneDX ML-BOM](https://cyclonedx.org/capabilities/mlbom/)
- [SLSA](https://slsa.dev/)
- [gitleaks](https://github.com/gitleaks/gitleaks)
- [Semgrep docs](https://semgrep.dev/docs/)
