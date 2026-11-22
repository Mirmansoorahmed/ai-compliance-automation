"""Demo: the vague-law classifier on the CV-screening story (Phase 5b), offline.

Uses the default local backend (open-source, hashed embedder offline — no model
download, no vendor call). For each state it prints, in plain words, the
expected outcome and the outcome the classifier produced, so a reader can see at
a glance whether the offline backend got it right.

  A. A claimed Annex III exception where the system profiles each applicant
     -> expected: the exception is REFUSED / escalated to a human.
  B. A solely-automated lending decision -> expected: Art. 22 condition MET.
  C. A human-in-the-loop decision        -> expected: Art. 22 condition ABSENT.

Routing legend (printed in the demo):
  route=ACT  -> the legal condition is met with enough confidence; apply the
                question's act_label (here ASK = send to a human / refuse the claim).
  route=NO   -> the condition is confidently absent; nothing to do.
  route=ASK  -> too uncertain to decide; a human decides (fail-safe).
  act_label  -> the catalog decision applied when the condition is met.
"""

from __future__ import annotations

from aca.vaguelaw.classify import ACT, ASK, NO, classify
from aca.vaguelaw.local_backend import LocalBackend
from aca.vaguelaw.questions import load_questions

# Each case: title, state text, question id, and what a correct answer looks
# like in plain words + the acceptable routes for "handled correctly".
_CASES = [
    {
        "title": "A. Annex III exception claimed, but the system profiles each applicant",
        "state": "We claim our CV tool is not high-risk because it only pre-sorts, but it "
                 "scores and ranks each applicant individually and profiles natural persons.",
        "qid": "AIA-6-3",
        "expected_words": "exception refused / escalated to a human (route ACT -> ASK)",
        "ok_routes": {ACT},
    },
    {
        "title": "B. Solely-automated lending decision",
        "state": "The model alone approves or rejects each loan application with no human "
                 "review and applies the result to the customer directly.",
        "qid": "GDPR-22",
        "expected_words": "Art. 22 condition met -> send to a human (route ACT -> ASK)",
        "ok_routes": {ACT},
    },
    {
        "title": "C. Human-in-the-loop lending decision",
        "state": "The model proposes a shortlist and a named loan officer reviews and signs "
                 "the final decision for each applicant.",
        "qid": "GDPR-22",
        "expected_words": "Art. 22 condition absent -> nothing to do (route NO)",
        "ok_routes": {NO},
    },
]

_ROUTE_WORDS = {
    ACT: "condition met -> apply act_label",
    NO: "condition absent -> nothing to do",
    ASK: "too uncertain -> a human decides",
}


def main() -> int:
    backend = LocalBackend()
    all_q = {q.id: q for q in load_questions()}

    print("Vague-law classifier demo — CV-screening story (offline local backend)\n")
    print("Backend: local (open-source; hashed embedder offline). No closed-vendor call.")
    print("Legend: route=ACT apply act_label | route=NO condition absent | route=ASK human decides.")
    print("        act_label = the catalog decision applied when the condition is met.\n")

    any_miss = False
    for case in _CASES:
        q = all_q[case["qid"]]
        r = classify(case["state"], [q], backend)[0]
        got_words = _ROUTE_WORDS[r.route]
        handled = r.route in case["ok_routes"]
        # An ASK (uncertain) is an acceptable fail-safe for an ACT case, but note it.
        acceptable = handled or (ACT in case["ok_routes"] and r.route == ASK)
        status = "OK" if handled else ("acceptable (fail-safe to human)" if acceptable else "MISS")
        if not acceptable:
            any_miss = True

        print(case["title"])
        print(f"   question  : {q.id} (act_label={q.act_label})")
        print(f"   expected  : {case['expected_words']}")
        print(f"   got       : route={r.route} ({got_words}); "
              f"act_label={q.act_label}; p_yes={r.p_yes}, confidence={r.confidence}")
        print(f"   verdict   : {status}")
        print()

    if any_miss:
        print("NOTE: at least one case was answered WRONG by the offline hashed embedder. "
              "This backend is a reproducible fallback, not the trained model; the real "
              "MiniLM backend (owner-run) is what these questions are tuned for. The miss "
              "is shown here rather than hidden.")
    else:
        print("All cases were handled correctly (or fail-safe to a human) by the offline "
              "backend. The real accuracy/ECE/ASK-rate are still measured by the owner "
              "with the trained model.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
