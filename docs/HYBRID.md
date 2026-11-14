# Hybrid profile runbook (Azure adapters)

The `hybrid` profile adds **optional** Azure adapters behind the same adapter
interfaces the `oss` profile uses. The `oss` profile stays the default and the
one CI guarantees; nothing here is required to run `make demo`, `make test`, or
`make report`.

> **Prerequisite — budget alert first (R15.3, DESIGN.md §15).** Do NOT enable any
> paid adapter until a budget alert is set on the Azure subscription. The lab
> account is **Azure for Students** (USD $90 credit, expires 7 November 2027, IU
> tenant). Set alerts at 50% and 80% of the credit, delivered to an address you
> monitor, and confirm them before sending a single hybrid request.

## What the hybrid adapters are (and are not)

| Adapter | Service | Role | Not |
|---|---|---|---|
| `prompt_shields` | Azure AI Content Safety — Prompt Shields | One signal: jailbreak / prompt-injection detection. Emits a label under the **separate** concept `PROMPT-INJECTION`, scored separately. | NOT a legal-element verdict; does not judge Art. 5 fit (Microsoft's own docs). |
| `judge` (stage 3) | Azure OpenAI / Azure AI Foundry | Optional LLM judge with a pinned rubric; lists legal elements + quoted spans as a label. **Off by default** even on hybrid. | NOT an authorization control; OPA still decides. |
| Entra ID | Microsoft Entra ID | Optional identity provider: normalises group claims. | NOT required; falls back to the fixture/Keycloak token. |

All three **degrade cleanly**: with no credentials they report unavailable and
are skipped, and a live failure (timeout / 401 / 403 / 429 / 5xx) makes the
adapter raise so the Guard marks it failed and the pipeline applies the
fail-safe tier (risky/unknown → `ask`) — never a silent allow.

## Required Azure resources

1. **Azure AI Content Safety** resource (for Prompt Shields), in an EU region if
   available on the student tenant (region/quota **unverified** — see DESIGN.md
   §15).
2. **Azure OpenAI** (or Azure AI Foundry) resource with a **deployed** chat model
   (the pinned deployment name), only if you enable the stage-3 judge. Access is
   often a separate approval.
3. **Entra ID** app registration able to issue group claims, only if you use the
   Entra identity provider (P1/P2 or student-plan limits **unverified**).

## Environment variables (no secrets in the repo)

Config is read from the environment only. Absent vars = adapter off.

```bash
# Prompt Shields (Azure AI Content Safety)
export ACA_PROMPT_SHIELDS_ENDPOINT="https://<resource>.cognitiveservices.azure.com"
export ACA_PROMPT_SHIELDS_KEY="<key>"
# optional, pinned default 2024-09-01
export ACA_PROMPT_SHIELDS_API_VERSION="2024-09-01"

# Azure OpenAI judge (stage 3) — only if you turn the judge on
export ACA_AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com"
export ACA_AZURE_OPENAI_KEY="<key>"
export ACA_AZURE_OPENAI_DEPLOYMENT="<deployment-name>"
# optional, pinned default 2024-10-21
export ACA_AZURE_OPENAI_API_VERSION="2024-10-21"

# Entra ID identity mapping — only if you use the Entra provider
export ACA_ENTRA_TENANT_ID="<tenant-guid>"
export ACA_ENTRA_CLIENT_ID="<app-client-id>"
```

To enable the stage-3 judge, also set `judge_enabled = true` under `[guard]` in
`config/hybrid.toml` (it is `false` by default).

## Cost notes (Azure for Students)

- Credit is small (USD $90) and expires; **every hybrid run spends it**. Keep
  runs short and the eval set small.
- Prompt Shields is billed per text record; the judge is billed per token.
  Favour the `oss` path for day-to-day work and reserve hybrid for a measured
  comparison run.
- Set the budget alert first (above). Turn paid adapters off again when done
  (`unset` the env vars or switch back to the `oss` profile).

## Running a real hybrid eval

With the env vars exported and a budget alert confirmed:

```bash
# 1) sanity: the Guard should list the vendor adapters it can reach
PYTHONPATH=src python3 -c "from aca.config import load_config; from aca.guard.service import SemanticGuard; print(SemanticGuard(load_config('hybrid')).adapter_names)"

# 2) run the hybrid eval (vendor path scored SEPARATELY from the local path)
make hybrid-eval
```

Without credentials, `make hybrid-eval` runs but every vendor metric prints
**TO BE MEASURED** — the harness never invents a hybrid number. A committed
hybrid result must come from a real credentialed run, recorded with a timestamp
and git SHA like the `oss` run under `eval/results/`.

## Safety recap

- Vendor/judge output is a *signal*, never a verdict — OPA decides.
- Prompt Shields uses a separate concept id, so it cannot be mistaken for an
  Art. 5 finding and is always scored separately.
- Fail-safe: adapter absent/timeout/401/403/429/5xx → `ask`, never a silent
  allow (tested in `tests/test_prompt_shields.py`, `tests/test_judge.py`,
  `tests/test_hybrid_wiring.py`).
- No hybrid metric is published until a real run exists.
