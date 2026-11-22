# Phase 7 — evidence pack v2

> Northwind Advisory for Halvaro Payments GmbH (fictional). Phase 7 collects the decisions from every enforcement point into one auditor-readable trace. Synthetic data only; not legal advice, not a conformity claim.

## What Phase 7 adds

- **One trace across all enforcement points** (`aca.evidence_pack.collect`) — for a single use case (CV pre-screening) it assembles the decisions made at the **editor hook**, the **CI gate**, the **deploy gate** (denied, then allowed after approvals), and the **runtime gateway link**, in order, using the same offline engines the phases use.
- **ISO/IEC 42001 and EU AI Act mapping table** — ties each control (impact assessment, human oversight, transparency, worker information, concern channel) to the EU AI Act / GDPR article and to **where it is enforced** in this system.
- **Approval and break-glass records** — the two distinct approvals required before deploy, and whether a break-glass override was used.
- **Auditor-readable PDF** (`aca.evidence_pack.build`) rendered with the existing report PDF writer, carrying the project disclaimers.

## No code, paths or hashes in the PDF body

The body is a plain-language narrative for an auditor. `aca.evidence_pack.render.assert_clean` enforces this: it rejects any text that contains a file path, a long hex hash, or a code fence, and `render_text` calls it before returning — so a regression cannot leak implementation detail into the pack. The build fails closed if the check trips.

## Run the demo

```bash
make check-evidence-demo        # or: scripts/demo_evidence.sh
```

It prints the auditor view: the ordered decision trace (editor → CI → deploy → runtime), the required artefacts and the two approvals, and the ISO 42001 / EU AI Act mapping. The trace shows the coherent story — the same prohibited use refused at the prompt, the secret blocked in CI, the first deploy denied for missing artefacts and then allowed after two approvals, and the runtime gateway denying the social-scoring tool call.

Build the PDF:

```bash
python3 -m aca.evidence_pack.build      # writes report/evidence-pack-v2.pdf
```

## Limits

- **The trace is assembled from the offline engines**, not harvested from a real production run; it is a faithful, deterministic reconstruction of what each point decides for this use case. Harvesting real OpenTelemetry spans from a live deployment is an operator step.
- **The mapping is illustrative** — our own-words reading of which control each point supports, not a certified mapping or a conformity claim.
- **Identities are roles**, not names; the pack carries no raw prompt/argument text (the decision records already drop it).

## To be run by the owner

- Point the collector at **real emitted spans** from a live deployment (the gateway, CI runs, deploy runs) to produce an evidence pack for an actual use case rather than the reconstructed demo trace.

## Scope note

Phase 7 is the auditor view over Phases 2–6. Phase 8 packages the whole thing to run on a clean machine (docker-compose) and signs the policy bundle.
