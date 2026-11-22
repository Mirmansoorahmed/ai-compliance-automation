# AGENTS.md — EU AI compliance (Codex / agents)

<!-- Generated from policy/catalog/catalog.yaml by adapters/generate_guides.py. Do not edit by hand. -->

Halvaro Payments GmbH (fictional client of Northwind Advisory) builds software with AI coding tools under the EU AI Act, GDPR and ISO/IEC 42001. These rules tell you what to avoid and what to declare. They are guidance: the compliance hook makes the actual decision on every prompt and tool call, and the CI and deploy gates enforce it. Synthetic data only; not legal advice and not a conformity claim.

This tool does not run the compliance hook as a blocking pre-tool check, so these rules are guidance for the model, not enforcement. The real gates are the CI check (guardrails-ci) on every pull request and, where wired, the MCP `compliance_check` tool. Treat a BLOCK item as something the PR will fail on.

## Never build these (refused — EU AI Act Art. 5 and hard security rules)

If a request amounts to one of these, the hook returns BLOCK and the tool refuses. This holds even when the wording avoids the obvious terms (for example, social scoring described only as joining behaviour data into a score and acting on it).

- **AIA-5-1-a** — Subliminal, manipulative or deceptive techniques causing significant harm (Art. 5(1)(a)).
- **AIA-5-1-b** — Exploiting vulnerabilities (age, disability, social or economic situation) (Art. 5(1)(b)).
- **AIA-5-1-ba** — Non-consensual intimate deepfakes (Art. 5(1)(ba) inserted by Reg. (EU) 2026/1744 (applies from 2 Dec 2026)).
- **AIA-5-1-bb** — Generating child sexual abuse material (Art. 5(1)(bb) inserted by Reg. (EU) 2026/1744 (applies from 2 Dec 2026)).
- **AIA-5-1-c** — Social scoring (Art. 5(1)(c); prohibited-practices guidelines).
- **AIA-5-1-d** — Predicting crime risk from profiling or personality alone (Art. 5(1)(d)).
- **AIA-5-1-e** — Untargeted scraping of facial images for recognition databases (Art. 5(1)(e)).
- **AIA-5-1-f** — Emotion recognition at the workplace or in education (Art. 5(1)(f)).
- **AIA-5-1-g** — Biometric categorisation of sensitive traits (Art. 5(1)(g)).
- **AIA-5-1-h** — Real-time remote biometric identification in public spaces for law enforcement (Art. 5(1)(h), 5(2)-(7)).
- **GDPR-32** — Security of processing (encryption, pseudonymisation, access control) (Art. 32).
- **SEC-LLM02** — Sensitive information disclosure (OWASP LLM02:2025).
- **SEC-LLM05** — Improper output handling (OWASP LLM05:2025).
- **SEC-LLM07** — System prompt leakage (OWASP LLM07:2025).
- **SEC-ASI03** — Identity and privilege abuse (OWASP ASI03).
- **SEC-ASI05** — Unexpected code execution (OWASP ASI05).
- **SEC-ASI06** — Memory and context poisoning (OWASP ASI06).
- **SEC-SECRETS** — Hard-coded secrets (CWE-798; gitleaks).
- **SEC-IAC-REGION** — Infrastructure: region, public exposure, encryption (Secure config; GDPR Art 44).
- **SEC-PROVENANCE** — Build provenance and signed artefacts (SLSA build provenance).

## High-risk — allowed, but it must be declared and gated (EU AI Act Annex III)

If you build one of these, keep working, but the hook returns WARN and lists the artefacts the law requires (risk assessment, DPIA, human-oversight plan, evaluation report, worker information, and a FRIA for credit or insurance). Declare the feature in `use-case.yaml`; the deploy gate blocks production until those artefacts exist and two different people have approved them.

- **AIA-A3-1a** — Remote biometric identification (not 1:1 verification) (Annex III point 1a).
- **AIA-A3-1b** — Biometric categorisation by sensitive or protected attributes (where not prohibited) (Annex III point 1b).
- **AIA-A3-1c** — Emotion recognition (outside work and education) (Annex III point 1c).
- **AIA-A3-2** — Safety component in critical infrastructure (digital infrastructure, road traffic, water, gas, heating, electricity) (Annex III point 2).
- **AIA-A3-3a** — Education: access, admission or assignment (Annex III point 3a).
- **AIA-A3-3b** — Education: evaluating learning outcomes (Annex III point 3b).
- **AIA-A3-3c** — Education: level of education a person will access (Annex III point 3c).
- **AIA-A3-3d** — Education: proctoring for prohibited behaviour in tests (Annex III point 3d).
- **AIA-A3-4a** — Employment: recruitment and selection (job ads targeting, CV filtering, candidate evaluation) (Annex III point 4a).
- **AIA-A3-4b** — Employment: promotion, termination, task allocation, performance and behaviour monitoring (Annex III point 4b).
- **AIA-A3-5a** — Public assistance benefits eligibility (by or for public authorities) (Annex III point 5a).
- **AIA-A3-5b** — Creditworthiness and credit scoring of natural persons (fraud detection excluded) (Annex III point 5b).
- **AIA-A3-5c** — Risk assessment and pricing in life and health insurance (Annex III point 5c).
- **AIA-A3-5d** — Emergency calls, dispatch and patient triage (Annex III point 5d).

## Secrets

Never put a key, token or password in code, config, prompts or rules files. The hook scans writes and shell commands and returns BLOCK for a secret; use a vault or environment variable instead.

## How a decision is made

- **BLOCK** — refused; the message names the rule.
- **ASK** — pauses for a human decision (ambiguous, or a solely-automated decision about a person).
- **WARN** — continue; obligations are shown and required before deployment.
- **ALLOW** — nothing to do.

The hook decides; this guide only explains. If the policy service is unreachable, the hook fails safe to ASK, and a secret write is still blocked.
