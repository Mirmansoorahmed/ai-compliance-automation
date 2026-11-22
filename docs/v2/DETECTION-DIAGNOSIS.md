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

## Implemented

Options A and C are now built (Phase A, then Phase C). Option B (the vague-law backend as an element decider) remains a proposal.

**Option A — similarity ASK tier.** A per-concept `ask_threshold` (in `policy/data/thresholds.json`) plus a `similarity_only` label flag: when the stage-1 margin (pos − neg) is at or above the threshold and the full element match is NOT met, the Guard sets `similarity_only`, and OPA (`compliance.tier`) routes it to **ASK — never four-eyes or deny**. `/v1/check` escalates an otherwise-ALLOW result to ASK with the plain reason "similar to <concept> (score x), elements not confirmed — human review", which the Claude/Kiro/Cursor and MCP adapters surface.

**Option C — element-level exemplars.** The `if concept_id == "AIA-5-1-c"` keyword block is replaced by per-element exemplar sets under `exemplars/elements/` (6+6 DE/EN per element, all 13 concepts, disjoint from tuning and held-out). An element is marked met when its max similarity to the element's positives exceeds its max similarity to the element's negatives by a per-element margin. A concept whose full match cannot be made safe has an element margin set to `null`, which **disables that concept's full match** so it falls back to Option A's ASK. Until the owner runs the real-model calibration, an uncalibrated concept keeps the prior behaviour (AIA-5-1-c via its keyword path; the other 12 cannot BLOCK), so the committed offline default introduces **no new BLOCK path** before validation.

### Calibration fixes after the first real-model run

The first real run raised recall but routed almost every benign case to review and introduced a few new false blocks. The fixes:

1. **Element margins are strictly > 0 (a floor, default 0.05) and calibrated to a cross-concept target.** A 0.0 margin over-marks. The element calibrator now drives the **false full-match rate to 0 counting cross-concept cases** — a benign case, or a positive of *another* concept, that marks every element of concept X is a false full match for X (because `decide()` inspects every concept's label). It scores **the exact element set the runtime adapter produces**, including the stage-0 keyword union for AIA-5-1-c, by running the real adapter with the candidate margins injected. If a concept can't reach 0, its full match is disabled and it is listed.
2. **Four-eyes requires a full, validated element match (`pattern_id` / all elements, not `similarity_only`).** The old "confidence ≥ high + min_elements" four-eyes path is removed. A `similarity_only` label — with any number of elements, at any confidence — is ASK at most. OPA and the Python mirror both enforce this, with tests at 1..n−1 elements.
3. **Metrics are split by tier.** The runner reports benign→**ASK**, benign→**four-eyes**, benign→**BLOCK** (= block + four-eyes, the false-block rate) and **review recall** = BLOCK + four-eyes + ASK, separately. The ASK calibrator's cap is on **benign→ASK + benign→four-eyes combined** (stated in the report), not the raw margin.
4. **One calibration command, correct order.** `python -m aca.eval.calibrate` calibrates element margins first, then the ASK thresholds **on top of that final element regime** (so the combined benign-review cap ≤ 0.15 actually holds after Phase C), and writes both files plus a combined report.
5. **Per-concept stability warnings.** The calibrator warns when a concept has fewer than 6 tuning positives, or when 0 tuning positives reach a full match at the chosen margins (strict recall will be 0).

### Why AIA-A3-4a has strict recall 0 (element design, not data volume)

AIA-A3-4a has 6 tuning positives and 6 held-out positives — enough data. Its strict recall is 0 because of **element design**: the element exemplars (`exemplars/elements/AIA-A3-4a.json`) are written as abstract meta-descriptions of the element ("This is about hiring new applicants." / "It scores and ranks the applicants.") rather than as realistic task phrasings like the tuning and held-out cases ("Auto-shortlist applicants by a learned fit score before any recruiter looks."). A real task sentence is not strongly similar to the abstract element description, so one or both elements fail to clear their margin and the full match never fires. The same shape affects the other low-recall concepts flagged by the calibrator (`AIA-5-1-d`, `AIA-A3-1c`, `AIA-A3-5c`, `GDPR-22`).

This is a **data-design** fix to make on the tuning/exemplar side (not the held-out set): rewrite each element's positives as concrete, task-shaped sentences that resemble how a developer actually phrases the request, keep the negatives as the realistic lawful look-alikes, and re-run the calibrator. It must be done without looking at the held-out texts. Until then those concepts carry strict recall 0 and rely on the Option A ASK tier to route confident near-matches to a human. **Do not tune the margins or exemplars against the held-out set.**

The real-model recall/false-block numbers from these are **to be run by the owner** (see the eval table placeholder in the README and the commands at the end of this change).

### Final calibration round (freeze)

After the first full real-model run, recall rose but almost every benign case was routed to review (benign→ASK ≈ 0.46) and a couple of new false blocks appeared. This round fixed the causes; **the detection design is now frozen — no more tuning.**

1. **Joint ASK calibration.** The ASK thresholds were calibrated per concept in isolation, but all 13 concepts run on every text, so the per-concept caps compounded to ~0.46 at runtime. The ASK calibrator is now **joint**: it precomputes each concept's label facts per tuning case once, then sets the per-concept thresholds so the **combined** benign→(ASK + four-eyes) rate across all concepts together is ≤ cap, maximising review recall. The optimiser is **greedy coordinate ascent** that tries every candidate threshold per concept and keeps the setting with the highest attack review recall while the cap holds, iterating to convergence (deterministic tie-break toward the higher threshold) — it does **not** stop at the first feasible point. (An earlier version did stop early and switched ASK off for every concept, wasting the whole 0.15 budget; fixed.) It writes a **tradeoff curve** (caps 0.05 / 0.10 / 0.15 / 0.20 / 0.30 → benign review and review recall) into the calibration report.
2. **Irreducible ASK removed.** A `partial_pattern` (or `confidence ≥ low`) used to add ASK that no threshold could remove. A partial now routes to ASK **only when it also clears the concept's calibrated `ask_threshold`**, and the stage-1 low-confidence ASK path was removed — so the ASK calibrator fully controls the ASK rate.
3. **Cross-concept robustness.** Element margins must be strictly > 0 and now beat the **best cross-concept negative** on tuning by a configurable `delta` (default 0.03). During calibration every other concept's benign and positive texts act as negatives for each element, so a floor margin is never chosen on a single boundary case (which is how GDPR-22 element margins had over-marked).
4. **Official-element intersection.** `decide()` and `compliance.tier` now intersect `elements_met` with the concept's **official** element set before counting a full match (a keyword/stage-A union name outside the set can no longer inflate the count). The adapter also emits `official_elements` and only official element names.
5. **Stronger calibrator audit.** The no-held-out test hooks `Path.read_text`/`read_bytes`, `os.open` and `builtins.open` (not only `load_yaml`) and asserts no held-out path is opened during a full combined calibration.

**Results and tradeoff (frozen).** Strict **BLOCK** is deliberately narrow — only a full, validated element match, calibrated to **0 false full matches on tuning**. The uncertain middle goes to **human review (ASK)**, never refusal, with the combined benign→review rate capped on tuning. **BLOCK stays conservative on purpose: a wrong block of a lawful product is worse than a review** — it stops a legitimate feature and teaches developers to bypass the gate, whereas a wrong ASK only asks a human to look. The residual risk is missed detections (a prohibited use slipping to ALLOW), which the held-out numbers measure.

The owner's final real-model run (multilingual MiniLM, calibration on tuning only), frozen joint ASK cap 0.15:

| Split | Precision | Strict recall | Review recall | False block | Benign→review |
|---|---|---|---|---|---|
| Legacy set (54) | 1.0 | 0.818 | 1.00 (22/22) | 0.0 | 0.188 |
| Legacy held-out (21) | 1.0 | 0.111 | 0.333 (3/9) | 0.0 | 0.333 |
| Tuning (210) | 1.0 | 0.18 | 0.79 (79/100) | 0.0 | 0.146 |
| Held-out v2 (156, never seen) | n/a (no BLOCKs) | 0.0 | 0.782 (61/78) | 0.0 | 0.256 |

Tradeoff curve (calibrator, tuning) — review recall / benign→review at each cap: 0.05 → 0.59 / 0.046; 0.10 → 0.69 / 0.10; 0.15 → 0.77 / 0.146; 0.20 → 0.77 / 0.20 (no gain); 0.30 → 0.86 / 0.30. **0.15 is the knee** — beyond it benign review rises without buying recall. Vague-law router: accuracy 0.829, ECE 0.160, ASK-rate 0.271 (48 cases). Concept-separation leave-one-out: 1.0 or 0.857 on all 13 concepts. Tests: 435 pytest pass (hashed embedder), OPA 32/32.

The honest reading: only `AIA-5-1-c` reaches full element matches on tuning, so strict auto-BLOCK recall on unseen data is 0.0 and the system leans on the review tier (78.2% of unseen attacks routed to a human), at the cost of 25.6% of unseen benign prompts also going to review. The 0.15 cap is tuning-only and does not fully transfer. Next: concrete per-element exemplars for the 12 concepts with zero full matches, a German-native embedder bake-off, and a re-check of the cap on a fresh held-out set.

**Owner commands (single calibrate + eval).** Set `ACA_REQUIRE_MODEL=1` so the real MiniLM model is used and every step **fails loudly** if it is absent (the vague-law and concept-separation CLIs previously fell back to the hashed embedder silently; they now use the same loader as the eval runner):

```bash
pip install -e ".[embeddings]"
export ACA_REQUIRE_MODEL=1
python -m aca.eval.calibrate --write   # tuning only: element margins (floor+delta) then JOINT ASK thresholds (combined benign review <= 0.15, recall maximised); writes both files + a report with the tradeoff curve
make eval                              # fills the per-concept table (5 columns) in the README
python -m aca.eval.concepts --require-model     # per-concept separation (fails loudly without the model)
python -m aca.vaguelaw.eval --require-model     # vague-law eval (fails loudly without the model)
opa test policy                        # must stay green
```
