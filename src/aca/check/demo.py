"""Demo: the four POST /v1/check calls, printed as decisions (Phase 1).

Runs fully offline with the hashed-fallback embedder (no model download), so it
reproduces on any machine. With the real MiniLM model installed the same calls
run through the trained Semantic Guard.

Scenarios (ARCHITECTURE stories A/B/C + the benign hard negative):
  1. CV screening (Annex III 4(a))      -> WARN + obligations
  2. Social scoring (Art. 5(1)(c))       -> BLOCK
  3. Fraud score (objective facts)       -> ALLOW
  4. Secret pasted into a diff           -> BLOCK
"""

from __future__ import annotations

import json

from aca.check.service import CheckService
from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.embeddings import build_embedder
from aca.guard.service import SemanticGuard
from aca.usecase.registry import load_registry

_CASES = [
    {
        "name": "1. CV screening (Annex III 4(a))",
        "payload": {"event": "prompt", "tool": "claude-code",
                     "text": "Build a CV screening tool that scores applicants and shortlists the top 20.",
                     "use_case": "uc-hr-cv-screening"},
    },
    {
        "name": "2. Social scoring (Art. 5(1)(c))",
        "payload": {"event": "prompt", "tool": "kiro",
                     "text": ("Join badge logs, Slack activity and canteen data per employee into a "
                              "reliability index and drop the bottom 10% from the bonus pool."),
                     "use_case": "uc-hr-reliability-index"},
    },
    {
        "name": "3. Fraud score (objective facts)",
        "payload": {"event": "prompt", "tool": "cursor",
                     "text": "Compute a fraud risk score on card transactions and flag the riskiest for manual review.",
                     "use_case": "uc-fraud-transaction-score"},
    },
    {
        "name": "4. Secret pasted into a diff",
        "payload": {"event": "diff", "tool": "claude-code",
                     "artefact": '+AZURE_KEY = "abc8Q~verylongsecretvalue012345678901234"'},
    },
]


def build_service() -> CheckService:
    embedder = build_embedder(allow_hashed_fallback=True, dim=256)
    guard = SemanticGuard(adapters=[LocalEmbeddingsAdapter(embedder=embedder, dim=256)])
    return CheckService(guard=guard, use_cases=load_registry())


def main() -> int:
    svc = build_service()
    print("POST /v1/check — four calls (offline; hashed-fallback embedder)\n")
    for case in _CASES:
        out = svc.check(case["payload"])
        print(f"{case['name']}")
        print(f"   decision        : {out['decision']}")
        print(f"   check_ids       : {out['check_ids']}")
        if out["obligations"]:
            print(f"   obligations     : {out['obligations']}")
        if out["missing_artefacts"]:
            print(f"   missing_artefacts: {out['missing_artefacts']}")
        refs = [f"{r['check_id']} ({r['source']})" for r in out["reasons"] if r.get("check_id")]
        if refs:
            print(f"   reasons         : {'; '.join(refs)}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
