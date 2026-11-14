# Four-eyes review and the feedback loop

This project does not let the running system change its own policy. Every hard
rule traces back to a human decision recorded through a pull request with two
distinct approvers. This note describes the loop; the code is in
`src/aca/review/` and the ownership gate in `.github/CODEOWNERS`.

## The loop

1. **Ambiguous decision.** OPA returns `ask` / `four-eyes` for a request whose
   labels sit between thresholds or hit some-but-not-all legal elements.
2. **A named reviewer records an interpretation.** Using the recorder
   (`aca.review.recorder`), the reviewer captures `owner`, `reason`, and a
   `decision` (`confirmed_prohibited_pattern` | `not_in_scope` | `needs_review`)
   plus the eval cases that justify the reading.
3. **A change set, not a runtime write.** The recorder writes an interpretation
   YAML under `interpretations/` and eval fixtures under `eval/cases/` on a new
   `review/<id>` branch and commits them. It never writes policy data
   (`policy/`), and it never mutates the register at runtime. This is enforced
   in code (`assert_no_policy_write`).
4. **PR + CI + four-eyes.** The branch opens a PR into the working branch. CI
   runs schema validation, `opa test`, the eval set, and coverage. CODEOWNERS
   requires review from the owning teams; two distinct approvers are needed so
   one person cannot both author and approve an auto-deny.
5. **Enforcement only after merge.** A `confirmed_prohibited_pattern`
   interpretation enables a hard `deny` only once it is approved and the
   corresponding `pattern_id` is added to the signed
   `policy/data/confirmed_prohibited_patterns.json` — a change that is itself a
   reviewed PR. Replaying the same prompt after merge then follows the new rule.

## Why this matters

Indeterminate legal concepts (e.g. *angemessen*, *Stand der Technik*) cannot be
fully automated. The system automates only an already-interpreted reading, and
the interpretation is owned by a named human and auditable in Git history. The
worst *automatic* outcome for an uninterpreted concept is "pause and ask a
human", never a silent allow and never a self-authored deny.
