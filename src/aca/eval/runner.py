"""Eval runner (R12).

Runs the labelled eval set through the Semantic Guard (local path) and measures:

- label precision / recall, reported **per language** (de, en),
- benign false-block rate (benign cases that wrongly assert the pattern),
- semantic-path latency p95 for stages 0-1 (the oss local path) and, separately,
  stages 2-3 (vendor/judge; empty on oss — reported as "not measured"),

then persists a results file with a timestamp and the git SHA so no number is
ever unprovenanced. Vendor-adapter scores are kept separate from the local path
(R12.5); on the oss profile there is no vendor path, so that section is null.

Ground truth: each case's ``expect_pattern`` (True for attack/positive,
False for benign/ambiguous). A "detection" is the Guard asserting the full
concept pattern (pattern_id present). Multi-turn "salami" cases are fed turn by
turn through a session context so accumulated elements can assert the pattern.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from aca.guard.adapters.local_embeddings import LocalEmbeddingsAdapter
from aca.guard.embeddings import build_embedder
from aca.guard.event import Event
from aca.guard.stages.stage_s import SessionContext

_EVAL_DIR = Path(__file__).resolve().parents[3] / "eval"
_CASES_DIR = _EVAL_DIR / "cases"
_RESULTS_DIR = _EVAL_DIR / "results"


def _git_sha(repo_root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[k]


@dataclass
class CaseResult:
    id: str
    lang: str
    category: str
    expect_pattern: bool
    detected_pattern: bool  # strict: full pattern asserted
    confidence: float
    elements_met: list[str]
    stage01_latency_ms: float
    tier: str = "allow"           # OPA tier for this case's labels
    routed_to_review: bool = False  # tier in {deny, four-eyes, ask}
    partial: bool = False          # a partial pattern (>=2 of 3) was emitted


@dataclass
class EvalReport:
    generated_ts: float
    git_sha: str
    profile: str
    embedder: str
    embedder_backend: str
    n_cases: int
    n_scored_cases: int
    per_language: dict
    benign_false_block_rate: float | None
    benign_routed_to_ask_rate: float | None
    latency_ms: dict
    prompt_injection: dict
    held_out: dict
    vendor_path: dict | None
    cases: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema": "eval-report/v2",
            "generated_ts": self.generated_ts,
            "git_sha": self.git_sha,
            "profile": self.profile,
            "embedder": self.embedder,
            "embedder_backend": self.embedder_backend,
            "n_cases": self.n_cases,
            "n_scored_cases": self.n_scored_cases,
            "per_language": self.per_language,
            "benign_false_block_rate": self.benign_false_block_rate,
            "benign_routed_to_ask_rate": self.benign_routed_to_ask_rate,
            "latency_ms": self.latency_ms,
            "prompt_injection": self.prompt_injection,
            "held_out": self.held_out,
            "vendor_path": self.vendor_path,
            "cases": self.cases,
        }


def load_cases(cases_dir: Path | None = None) -> list[dict]:
    from aca.register.yamlio import load_yaml

    base = cases_dir or _CASES_DIR
    return [load_yaml(p) for p in sorted(base.glob("*.yaml"))]


def _run_case(case: dict, adapter: LocalEmbeddingsAdapter, policy_data) -> CaseResult:
    from aca.guard.stages.exemplars import load_concept
    from aca.guard.stages.stage_s import accumulate_session_elements
    from aca.policy.decide import decide

    concept_id = case.get("concept_id", "AIA-5-1-c")
    lang = case.get("lang", "en")
    required = set(load_concept(concept_id, adapter._embedder).elements)

    start = time.perf_counter()
    if case.get("multi_turn"):
        # Feed turns; aggregate elements AND behaviour-source hits across the
        # session window so split ("salami") requests combine (item 3).
        per_turn = [
            adapter.detect(Event(text=turn, language=lang))
            for turn in case.get("turns", [])
        ]
        accumulated, _hits = accumulate_session_elements(per_turn, concept_id)
        confidence = max(
            (l.get("confidence", 0.0) for labels in per_turn for l in labels
             if l.get("concept_id") == concept_id),
            default=0.0,
        )
        elements_met = sorted(accumulated)
        met_count = len(required & accumulated)
        full_match = met_count == len(required)
        partial = (not full_match) and met_count >= 2 and len(required) >= 3
        # Build one synthesised session label for the policy decision.
        label = {
            "concept_id": concept_id,
            "confidence": confidence,
            "elements_met": elements_met,
            "elements_total": len(required),
            "partial_pattern": partial,
        }
        if full_match:
            label["pattern_id"] = load_concept(concept_id, adapter._embedder).pattern_id
        labels = [label]
    else:
        labels = adapter.detect(Event(text=case.get("text", ""), language=lang))
        label = next((l for l in labels if l["concept_id"] == concept_id), None)
        full_match = bool(label and label.get("pattern_id"))
        partial = bool(label and label.get("partial_pattern"))
        confidence = label.get("confidence", 0.0) if label else 0.0
        elements_met = label.get("elements_met", []) if label else []
    latency_ms = (time.perf_counter() - start) * 1000.0

    tier = decide(labels, policy_data)

    return CaseResult(
        id=case["id"],
        lang=lang,
        category=case.get("category", "unknown"),
        expect_pattern=bool(case.get("expect_pattern", False)),
        detected_pattern=bool(full_match),
        confidence=round(confidence, 4),
        elements_met=elements_met,
        stage01_latency_ms=round(latency_ms, 3),
        tier=tier,
        routed_to_review=tier in ("deny", "four-eyes", "ask"),
        partial=bool(partial),
    )


def _prf(results: list[CaseResult]) -> dict:
    tp = sum(1 for r in results if r.expect_pattern and r.detected_pattern)
    fp = sum(1 for r in results if not r.expect_pattern and r.detected_pattern)
    fn = sum(1 for r in results if r.expect_pattern and not r.detected_pattern)
    tn = sum(1 for r in results if not r.expect_pattern and not r.detected_pattern)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    # Routed-to-review recall: of the attacks (expect_pattern), how many were
    # routed to a human (deny/four-eyes/ask) rather than allowed. The partial
    # rule lifts this above strict recall without touching strict recall.
    attacks = [r for r in results if r.expect_pattern]
    routed = sum(1 for r in attacks if r.routed_to_review)
    routed_to_review = round(routed / len(attacks), 4) if attacks else None
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "routed_to_review": routed_to_review,
        "n": len(results),
    }


def _benign_rates(results: list["CaseResult"]) -> dict:
    """False-block (strict) and routed-to-ask rates on benign/ambiguous cases."""
    benign = [r for r in results if r.category in ("benign", "ambiguous")]
    if not benign:
        return {"benign_false_block_rate": None, "benign_routed_to_ask_rate": None, "n_benign": 0}
    # Strict false block = a benign case that asserts the FULL pattern (deny tier
    # once confirmed). Routed-to-ask = benign case sent to a human (the cost of
    # the partial rule; should stay low).
    false_blocks = sum(1 for r in benign if r.detected_pattern)
    routed_ask = sum(1 for r in benign if r.routed_to_review)
    return {
        "benign_false_block_rate": round(false_blocks / len(benign), 4),
        "benign_routed_to_ask_rate": round(routed_ask / len(benign), 4),
        "n_benign": len(benign),
    }


def run_eval(
    *,
    cases_dir: Path | None = None,
    repo_root: Path | None = None,
    profile: str = "oss",
    dim: int = 256,
) -> EvalReport:
    root = repo_root or Path(__file__).resolve().parents[3]
    embedder = build_embedder(allow_hashed_fallback=True, dim=dim)
    adapter = LocalEmbeddingsAdapter(embedder=embedder, dim=dim)

    # Eval uses the production thresholds with an EMPTY confirmed-pattern list
    # (the default), so a full match routes to four-eyes and a partial to ask —
    # never an auto-deny during measurement.
    from aca.policy.decide import PolicyData, load_policy_data

    base_policy = load_policy_data()
    policy_data = PolicyData(thresholds=base_policy.thresholds, confirmed_prohibited_patterns=[])

    all_cases = load_cases(cases_dir)
    # The local path scores the legal concept (AIA-5-1-c). PROMPT-INJECTION cases
    # are for the vendor path (Prompt Shields) and are reported separately.
    aia_cases = [c for c in all_cases if c.get("concept_id") == "AIA-5-1-c"]
    injection_cases = [c for c in all_cases if c.get("concept_id") == "PROMPT-INJECTION"]

    results = [_run_case(c, adapter, policy_data) for c in aia_cases]

    per_language = {}
    for lang in sorted({r.lang for r in results}):
        per_language[lang] = _prf([r for r in results if r.lang == lang])
    per_language["overall"] = _prf(results)

    benign_rates = _benign_rates(results)
    benign_false_block_rate = benign_rates["benign_false_block_rate"]
    benign_routed_to_ask_rate = benign_rates["benign_routed_to_ask_rate"]

    # Held-out set: NEW cases not used while tuning stage-0 vocab/exemplars,
    # scored separately so improvements are not just fit to the training texts.
    held_out = _score_held_out(adapter, policy_data, root)

    stage01 = [r.stage01_latency_ms for r in results]
    latency = {
        "stage_0_1_p95_ms": _percentile(stage01, 95),
        "stage_0_1_count": len(stage01),
        # Stages 2-3 are vendor/judge; off on oss -> not measured here.
        "stage_2_3_p95_ms": None,
        "stage_2_3_note": "not measured (vendor/judge path off on oss profile)",
    }

    # PROMPT-INJECTION set: the local path does not detect injection (that is the
    # vendor Prompt Shields path), so on oss these are counted but NOT scored —
    # precision/recall are TO BE MEASURED until a credentialed hybrid run.
    pi_by = {"injection": 0, "clean": 0}
    for c in injection_cases:
        cat = c.get("category")
        if cat in pi_by:
            pi_by[cat] += 1
    prompt_injection = {
        "n_cases": len(injection_cases),
        "by_category": pi_by,
        "scored_by": "vendor Prompt Shields path (hybrid)",
        "precision": "TO BE MEASURED",
        "recall": "TO BE MEASURED",
        "note": "Local path does not label injection; run make hybrid-eval with Azure creds.",
    }

    backend = "sentence-transformers" if embedder.version.startswith("st:") else "hashed-fallback"

    return EvalReport(
        generated_ts=time.time(),
        git_sha=_git_sha(root),
        profile=profile,
        embedder=embedder.version,
        embedder_backend=backend,
        n_cases=len(all_cases),
        n_scored_cases=len(results),
        per_language=per_language,
        benign_false_block_rate=benign_false_block_rate,
        benign_routed_to_ask_rate=benign_routed_to_ask_rate,
        latency_ms=latency,
        prompt_injection=prompt_injection,
        held_out=held_out,
        vendor_path=None,  # no vendor adapter on oss; scored separately when present
        cases=[r.__dict__ for r in results],
    )


def _score_held_out(adapter: LocalEmbeddingsAdapter, policy_data, root: Path) -> dict:
    """Score the held-out set (eval/heldout/) separately from the tuning set."""
    held_dir = root / "eval" / "heldout"
    if not held_dir.exists():
        return {"n_cases": 0, "note": "no held-out set present"}
    cases = load_cases(held_dir)
    aia = [c for c in cases if c.get("concept_id") == "AIA-5-1-c"]
    results = [_run_case(c, adapter, policy_data) for c in aia]
    per_language = {}
    for lang in sorted({r.lang for r in results}):
        per_language[lang] = _prf([r for r in results if r.lang == lang])
    per_language["overall"] = _prf(results)
    benign_rates = _benign_rates(results)
    return {
        "n_cases": len(cases),
        "n_scored_cases": len(results),
        "per_language": per_language,
        "benign_false_block_rate": benign_rates["benign_false_block_rate"],
        "benign_routed_to_ask_rate": benign_rates["benign_routed_to_ask_rate"],
        "note": "NEW cases not used while tuning; scored separately (no fit to these texts).",
        "cases": [r.__dict__ for r in results],
    }


def write_report(report: EvalReport, *, results_dir: Path | None = None) -> Path:
    base = results_dir or _RESULTS_DIR
    base.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(report.generated_ts))
    path = base / f"eval-{stamp}-{report.git_sha[:8]}.json"
    path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    # Also update a stable 'latest' pointer for the report/README tooling.
    (base / "latest.json").write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    return path


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI glue
    report = run_eval()
    path = write_report(report)
    print(f"eval report written: {path}")
    print(f"  git_sha={report.git_sha}  backend={report.embedder_backend}  "
          f"cases={report.n_cases} scored={report.n_scored_cases}")
    for lang, m in report.per_language.items():
        print(f"  [{lang}] precision={m['precision']} strict_recall={m['recall']} "
              f"routed_to_review={m['routed_to_review']} n={m['n']}")
    print(f"  benign_false_block_rate={report.benign_false_block_rate} "
          f"benign_routed_to_ask_rate={report.benign_routed_to_ask_rate}")
    print(f"  stage_0_1_p95_ms={report.latency_ms['stage_0_1_p95_ms']}")
    ho = report.held_out
    if ho.get("per_language"):
        o = ho["per_language"]["overall"]
        print(f"  held-out: n={ho['n_cases']} precision={o['precision']} "
              f"strict_recall={o['recall']} routed_to_review={o['routed_to_review']} "
              f"false_block={ho['benign_false_block_rate']}")
    print(f"  prompt_injection: {report.prompt_injection['n_cases']} cases "
          f"(precision/recall {report.prompt_injection['precision']})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
