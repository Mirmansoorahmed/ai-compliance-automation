"""Demo: the vague-law classifier on the CV-screening story (Phase 5b), offline.

Uses the default local backend (open-source, hashed embedder offline — no model
download, no vendor call). It answers the Art. 6(3) exception question and the
GDPR Art. 22 solely-automated question for three states:

  A. A claimed Annex III exception where the system profiles each applicant
     -> the exception is refused (Art. 6(3) condition met -> ACT its ASK label).
  B. A solely-automated lending decision -> Art. 22 condition met.
  C. A human-in-the-loop decision -> Art. 22 condition absent.

Low-confidence answers route to ASK (a human). The closed Jev backend is never
constructed here.
"""

from __future__ import annotations

from aca.vaguelaw.classify import classify
from aca.vaguelaw.local_backend import LocalBackend
from aca.vaguelaw.questions import load_questions

_STATES = [
    ("A. Annex III exception claimed, but the system scores each applicant individually",
     "We claim our CV tool is not high-risk because it only pre-sorts, but it scores and ranks each applicant individually and profiles natural persons.",
     ["AIA-6-3"]),
    ("B. Solely-automated lending decision",
     "The model alone approves or rejects each loan application with no human review and applies the result to the customer directly.",
     ["GDPR-22"]),
    ("C. Human-in-the-loop lending decision",
     "The model proposes a shortlist and a named loan officer reviews and signs the final decision for each applicant.",
     ["GDPR-22"]),
]


def main() -> int:
    backend = LocalBackend()
    all_q = {q.id: q for q in load_questions()}
    print("Vague-law classifier demo — CV-screening story (offline local backend)\n")
    print("Backend: local (open-source; hashed embedder offline). No closed-vendor call.\n")
    for title, state, qids in _STATES:
        questions = [all_q[q] for q in qids if q in all_q]
        routings = classify(state, questions, backend)
        print(title)
        for r in routings:
            print(f"   question {r.question_id}: route={r.route} "
                  f"(act_label={r.act_label}, p_yes={r.p_yes}, confidence={r.confidence})")
        print()
    print("Note: offline hashed-embedder probabilities are a smoke signal; the real "
          "accuracy/ECE/ASK-rate are measured by the owner with the trained model.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
