# Phase 1 — one API, four decisions

> Northwind Advisory for Halvaro Payments GmbH (fictional). This explains, in plain language, the Phase 1 build: one HTTP endpoint that turns a developer's action into one of four decisions, with the obligations the law attaches. Synthetic data only; not legal advice, not a conformity claim.

## What Phase 1 adds

Before Phase 1 the service only had `POST /v1/labels` (the Semantic Guard emitting labels). Phase 1 adds **`POST /v1/check`**: a single endpoint for every point where a developer acts — typing a prompt, the agent calling a tool or writing a file, a pull-request diff, or a deploy. It runs the Semantic Guard and reads the repo's `use-case.yaml`, asks OPA, and returns one decision plus what the law requires.

`POST /v1/labels` is unchanged and still works.

## The four decisions

| Decision | Meaning | Example in this phase |
|---|---|---|
| **BLOCK** | Refused. A prohibited practice or a hard security rule. | Social scoring (EU AI Act Art. 5(1)(c)); a secret in a diff. |
| **ASK** | Pause for a human. Ambiguous, or a solely-automated decision about a person. | A 2-of-3 social-scoring match; a CV tool declared *solely automated* (GDPR Art. 22). |
| **WARN** | Keep building, but obligations are now required before deploy. | CV screening or credit scoring (EU AI Act Annex III high-risk). |
| **ALLOW** | Nothing to do; logged. | Fraud scoring on objective transaction facts (the Annex III 5(b) fraud exception). |

Precedence is **BLOCK > ASK > WARN > ALLOW**: the strictest decision among the checks that fired wins. **Fail-safe:** if anything goes wrong producing a decision (the Guard is down, an error), the answer is **ASK** — never a silent ALLOW.

## The request and response

Request (same shape for every tool and event):

```json
{ "event": "prompt | tool | diff | deploy",
  "tool": "claude-code | cursor | copilot | codex | kiro | mcp | ci | gate",
  "text": "Build a CV screening tool ...",
  "artefact": "<diff text, for tool/diff events>",
  "use_case": "uc-hr-cv-screening" }
```

Response:

```json
{ "decision": "WARN",
  "check_ids": ["AIA-A3-4a", "GDPR-22", "GDPR-35", "AIA-26-7", "DE-BETRVG-87"],
  "reasons": [ { "check_id": "AIA-A3-4a", "decision": "WARN",
                 "source": "Annex III point 4a", "title": "Employment: recruitment ...",
                 "obligations": ["risk_management", "dpia", "oversight_plan", "eval_report", "worker_information"] } ],
  "obligations": ["risk_management", "dpia", "oversight_plan", "eval_report", "worker_information"],
  "missing_artefacts": ["risk_management", "dpia", "oversight_plan", "eval_report", "worker_information"] }
```

- **`check_ids`** — the catalog checks that fired (e.g. `AIA-A3-4a` is EU AI Act Annex III point 4(a)).
- **`reasons`** — one per check, each naming its legal source, so the article reference travels with the decision.
- **`obligations`** — the artefacts the law requires before this use case may deploy (from the catalog).
- **`missing_artefacts`** — the obligations whose file is not yet present/approved in `use-case.yaml`.

## How a decision is formed

1. **Semantic Guard** labels the text (it has real coverage for Art. 5(1)(c) social scoring today). A full three-element match fires `AIA-5-1-c` (BLOCK). A 2-of-3 match is carried through as a *partial* pattern and routed to **ASK**, never ALLOW.
2. **Deterministic secret scan** runs on `tool` and `diff` events. A hit fires `SEC-SECRETS` (BLOCK). This is a dependency-free regex scanner; CI runs gitleaks as the fuller check.
3. **`use-case.yaml`** declares the Annex III area. Each declared area maps to its catalog check (`4(a)` → `AIA-A3-4a` WARN) and pulls in the companion legal duties the catalog lists for it (GDPR Art. 22, Art. 35 DPIA, Art. 26(7) worker information, § 87 BetrVG). Those companions add their article references and obligations but are **clamped to WARN** in the bundle — they are duties attached to a high-risk use case, not independent gates. GDPR Art. 22 escalates the bundle to **ASK** only when the use case is declared *solely automated*.

OPA is the only decision point. `policy/check.rego` (package `compliance.check`) implements the precedence and reads the catalog + obligations data generated from `catalog.yaml`. `src/aca/check/decide.py` is a line-for-line Python mirror so the service and the tests run in-process without an `opa` binary; `policy/check_test.rego` and `tests/test_check_mirror.py` check the same cases. The existing `compliance.tier` policy (deny/four-eyes/ask/allow for labels) is untouched.

## The required Phase 1 mappings

| Use / event | Checks | Decision | Obligations added |
|---|---|---|---|
| CV screening (Annex III 4(a)) | `AIA-A3-4a` + GDPR-22, GDPR-35, AIA-26-7, DE-BETRVG-87 | **WARN** | risk management, DPIA, oversight plan, eval report, worker information |
| Credit scoring (Annex III 5(b)) | `AIA-A3-5b` + AIA-27 (FRIA), GDPR-22, GDPR-35 | **WARN** | risk management, DPIA, **FRIA**, oversight plan, eval report |
| Social scoring (Art. 5(1)(c)) | `AIA-5-1-c` | **BLOCK** | — |
| Fraud detection (objective facts) | none (Annex III 5(b) fraud exception) | **ALLOW** | — |
| Secret in a tool/diff | `SEC-SECRETS` | **BLOCK** | — |

## Run it

```bash
make check-demo          # or: scripts/demo_v1_check.sh
```

Output (offline, hashed-fallback embedder):

```
1. CV screening (Annex III 4(a))  -> WARN  (AIA-A3-4a + GDPR-22/35, AIA-26-7, BetrVG-87; 5 obligations, all missing)
2. Social scoring (Art. 5(1)(c))  -> BLOCK (AIA-5-1-c)
3. Fraud score (objective facts)  -> ALLOW
4. Secret pasted into a diff      -> BLOCK (SEC-SECRETS)
```

With the real multilingual MiniLM model installed, the same calls run through the trained Semantic Guard; the demo uses the deterministic fallback so it reproduces anywhere.

## Scope note

Phase 1 is the policy core and the API. It does not yet include the IDE adapters (Phase 2), the CI gate (Phase 3) or the deploy gate (Phase 4) that enforce these decisions; those are in the build plan. The decisions and obligations here are the single contract all of those will use.
