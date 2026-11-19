# Phase 5b — the vague-law classifier

> Northwind Advisory for Halvaro Payments GmbH (fictional). Some legal tests are not keyword-matchable — whether an Annex III exception really holds, whether a decision is "solely automated". Phase 5b answers these open questions with a pluggable backend. Synthetic data only; not legal advice, not a conformity claim.

## What Phase 5b adds

- **`DecisionBackend` interface** (`aca.vaguelaw.backend`) — `decide(state, questions) -> [Answer]`, each `Answer` a yes/no plus `p_yes` in [0, 1].
- **`LocalBackend`** (default) — open-source, lazy-loaded MiniLM similarity; compares the state to each question's positive/negative exemplars and turns the margin into a probability. Falls back to the deterministic hashed embedder offline, so it runs anywhere with no download and no vendor call.
- **`FakeBackend`** — deterministic, scriptable; used by every test and available for demos. No model.
- **`JevBackend`** — optional closed vendor (TypeSafe `jev-1`), **off by default**. It refuses to construct unless the operator sets `VAGUELAW_JEV_ENABLED=1` and `VAGUELAW_JEV_API_KEY` (their own key) and passes `synthetic_ok=True`. Using it is flagged as a GDPR **Art. 44 international transfer** and a vendor-risk decision; only synthetic data may be sent; only the public HTTP API is used (no vendor code copied). It is never constructed in tests or the default demo.
- **Question sets** (`config/vaguelaw/questions.yaml`) — derived from `catalog.yaml`: the Art. 6(3) Annex III exception, GDPR Art. 22 solely-automated decisions, Art. 5(1)(a) manipulation, Art. 50 transparency. Each carries `act_label`, `act_threshold` and `ask_below`. (Kept under `config/` rather than `policy/` so OPA does not load it as bundle data.)
- **Routing** (`aca.vaguelaw.classify`) — per question: `p_yes >= act_threshold` → **ACT** (apply the question's catalog label), `p_yes <= 1 - act_threshold` → **NO**, otherwise → **ASK** (a human). Low confidence never silently resolves.
- **Eval harness** (`aca.vaguelaw.eval`) — accuracy, expected calibration error (ECE) and ASK rate over a labelled set (`eval/vaguelaw/`). With the fake or offline backend these are a smoke signal; the real numbers are **to be measured** by the owner.

## Run the demo

```bash
make check-vaguelaw-demo        # or: scripts/demo_vaguelaw.sh
```

Offline output (default local backend, no vendor call):

```
A. Annex III exception claimed, but the system scores each applicant individually
   question AIA-6-3: route=ACT (act_label=ASK, ...)
B. Solely-automated lending decision
   question GDPR-22: route=ACT (act_label=ASK, ...)
C. Human-in-the-loop lending decision
   question GDPR-22: route=NO (act_label=ASK, ...)
```

The demo prints, for each case, the **expected** outcome and what the classifier **got**, with a one-line routing legend:

- `route=ACT` — the legal condition is met with enough confidence; apply the question's `act_label` (here ASK = refuse the claim / send to a human).
- `route=NO` — the condition is confidently absent; nothing to do.
- `route=ASK` — too uncertain to decide; a human decides (fail-safe).
- `act_label` — the catalog decision applied when the condition is met.

A claimed Annex III exception on a system that profiles each applicant is **refused** (case A: route ACT → ASK, the Art. 6(3) condition is met); a solely-automated lending decision triggers the Art. 22 question; a human-in-the-loop decision does not. If the **offline hashed embedder answers a case wrong**, the demo prints `verdict: MISS` and says so explicitly (it does not hide it) — the offline backend is a reproducible fallback, not the trained model the questions are tuned for.

## To be run by the owner

- **Real accuracy / ECE / ASK-rate** — run the eval with the trained MiniLM model (and a larger 50–100-case-per-set labelled corpus). This repo ships the harness and a few seed cases; the numbers are **to be measured**.
- **The Jev backend** — only the operator enables it, with their own key, on synthetic data, having accepted the Art. 44 transfer and vendor-risk flag. It is never exercised here.

## Limits

- The local backend is a **similarity** classifier over short exemplars, not a trained legal model; the offline hashed fallback is weaker still (smoke only).
- The question set is a seed (four questions); expanding coverage and tuning thresholds per question is the measured work.
- `act_label` applies the catalog decision for the question's check; the vague-law layer answers the condition, it does not re-decide the tier.

## Scope note

Phase 5b sits on top of Phase 5's wider detection: detection says *which* concept a request touches; the vague-law classifier answers the *open legal condition* that decides whether a high-risk or prohibited reading applies. The closed vendor path stays optional and operator-controlled.
