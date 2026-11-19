# Detection diagnosis — why held-out v2 predicts 0 positives

> Northwind Advisory for Halvaro Payments GmbH (fictional). A code-level diagnosis of the Phase-5 held-out result, with options to raise recall. **No code is changed here** — this is analysis and a proposal. Synthetic data only; not legal advice.

## The observation

On the `eval/heldout_v2/` set the detector predicts **0 positives out of the attack cases**, and every miss has `elements_met = []`. The real multilingual MiniLM model is loaded, so this is not an embedding-quality problem — it is a wiring problem in the legal-element step.

## Why it happens (from the code)

A concept is predicted as a full pattern only when **every** legal element is marked met. That is decided in `src/aca/guard/adapters/local_embeddings.py`:

- `total = len(index.elements)` and `full_match = met_count == total`.
- `pattern_id` (the full-pattern assertion) is set only when `full_match` is true.

`elements_met` is produced by `run_stage1` in `src/aca/guard/stages/stage1.py`. The decisive lines:

```
elements_met: list[str] = []
if index.concept_id == "AIA-5-1-c":
    if signals.behaviour_hits >= 2 or (signals.has_pii and signals.behaviour_hits >= 1):
        elements_met.append("person_identifiable_behaviour_join")
    if signals.score_hits >= 1:
        elements_met.append("aggregated_score_or_ranking")
    if signals.adverse_hits >= 1:
        elements_met.append("adverse_action")
```

Two facts follow directly:

1. **Element marking exists only for `AIA-5-1-c`.** The block is guarded by `if index.concept_id == "AIA-5-1-c"`. For the other 12 concepts (Art. 5(1)(a/b/d/f/g), Annex III 1c/4a/4b/5b/5c, GDPR 9/22) nothing is ever appended, so `elements_met` stays `[]`, `met_count` is 0, `full_match` is always false, and no positive is ever predicted. This alone explains 0 positives for every held-out case outside `AIA-5-1-c`.

2. **Even for `AIA-5-1-c`, the elements come from stage-0 keyword counters, not from the embedding.** `behaviour_hits`, `score_hits` and `adverse_hits` are substring counts against fixed hint tables in `src/aca/guard/stages/stage0.py` (`_BEHAVIOUR_HINTS`, `_SCORE_HINTS`, `_ADVERSE_HINTS`). The thresholds are `behaviour_hits >= 2` (or PII + 1), `score_hits >= 1`, `adverse_hits >= 1`. A **paraphrased** held-out sentence that deliberately avoids those literal substrings (e.g. "obedience rating", "freeze pay for the lowest band" instead of "reliability index", "bottom 10% of the bonus pool") produces low hit counts, so one or more elements are not marked and `full_match` fails — exactly what a held-out set that is disjoint from the exemplars/tuning is designed to probe.

So the embedding similarity (`confidence = relu(pos_sim − neg_sim)`) is computed but **does not drive element marking at all** — it only sets `confidence`. The element gate, and therefore the full-pattern decision, is keyword-driven and single-concept. The held-out set, being paraphrased and covering 13 concepts, lands almost entirely outside that gate.

## Why confidence being high doesn't help today

`run_stage1` returns a real `confidence` from the MiniLM margin, and a paraphrased attack can have a high `confidence`. But nothing downstream turns high similarity into a routing: OPA (`compliance.check` / `compliance.tier`) keys off `pattern_id` (full match) and the `partial_pattern` flag, and `partial_pattern` itself is `met_count >= 2` — again element-driven. A confident embedding match with `elements_met = []` is neither a full nor a partial pattern, so it is allowed.

## Options to raise recall without raising false blocks

These are proposals; none is implemented. Each keeps BLOCK conservative and routes uncertainty to a human.

### Option A — an exemplar-similarity tier that routes to ASK (not BLOCK)

Add a tier: when `confidence` (the positive-minus-negative margin) is above a per-concept `ask_threshold` but the elements are not fully met, emit a new `similarity_only` signal and route it to **ASK**, never BLOCK. The hard-negative margin already suppresses lawful look-alikes ("fraud risk score"), so this leans on the part of the pipeline the model is good at.

- **Pros:** works for all 13 concepts with no new keyword tables; uses the trained model directly; a paraphrase that is clearly near a positive and far from the hard negatives gets a human review instead of silent allow.
- **Cons:** needs a per-concept threshold calibrated on the **tuning** set (never the held-out set) with its ECE measured; raises the ASK rate, so the benign-routed-to-ask rate must be watched; still never auto-BLOCKs, so a true prohibited use is caught as ASK, not refused.
- **Trade-off:** higher recall-to-review at the cost of more human review; zero change to the false-BLOCK rate (BLOCK still requires the full element match).

### Option B — the vague-law backend as a second stage

When stage 1 is confident but elements are unmet, call the Phase-5b `DecisionBackend` (local MiniLM/NLI) with the concept's legal question(s) and use its `ACT/NO/ASK` routing to decide element presence (e.g. "does this describe creditworthiness scoring of a natural person?"). A confident ACT marks the element; low confidence → ASK.

- **Pros:** reuses existing, tested machinery; gives an auditable per-element answer with a probability; naturally multilingual; the fake backend keeps tests deterministic.
- **Cons:** more latency per event (an extra inference); needs a question per element, not just per concept, so the question set must grow; calibration (accuracy/ECE) must be measured per question on the tuning set before it gates anything.
- **Trade-off:** the most faithful to "legal elements", but the largest build and the one most dependent on the classifier's calibration; keep it ASK-only until the measured ECE is low.

### Option C — element-level exemplars (generalise the stage-1 element logic)

Replace the `if concept_id == "AIA-5-1-c"` keyword block with **per-element exemplar sets**: each legal element gets its own small positive/negative exemplar list, and an element is marked met when the text's similarity to that element's positives clears a margin over its negatives. The concept is a full match when all its elements clear their own margins.

- **Pros:** removes the single-concept hard-coding and the brittle keyword tables; element marking becomes embedding-driven and consistent with how confidence is already computed; scales to every concept by adding data, not code.
- **Cons:** the most data work (element-level exemplars for ~30 elements, DE+EN); per-element thresholds to calibrate on tuning; risk of raising false positives if an element's negatives are weak — so the full-match → BLOCK path must be validated carefully on tuning before trusting it.
- **Trade-off:** the cleanest long-term design and the only one that can lift **strict** recall (not just routed-to-review), but it touches the BLOCK path, so it needs the most careful false-block validation.

## Recommended sequencing (proposal only)

1. **Option A first** (ASK-only similarity tier) — it is low-risk, model-driven, and cannot raise false BLOCKs; measure its ASK-rate and benign-routed-to-ask on the tuning set.
2. **Option C** for the concepts that most need strict recall, once element-level exemplars exist and are validated on tuning.
3. **Option B** where a genuine legal judgement (Art. 6(3), Art. 22) is the bottleneck, reusing the vague-law classifier.

In every option: calibrate only on the **tuning/dev** set, never the held-out set; keep BLOCK gated on a full, validated element match; and route everything uncertain to ASK.
