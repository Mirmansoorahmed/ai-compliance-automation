"""Eval harness for the vague-law classifier (Phase 5b).

Scores a labelled set of (state, question_id, expected_yes) cases through a
backend and reports accuracy, expected calibration error (ECE), and the ASK rate
(the share routed to a human). With the FakeBackend or the offline hashed
LocalBackend these are a SMOKE signal only; the real accuracy/ECE on the trained
model is **to be measured by the owner**.

Case file shape (eval/vaguelaw/*.yaml):
    id: vl-art22-pos-01
    question_id: GDPR-22
    state: "The model alone approves or rejects the loan ..."
    expect_yes: true
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from aca.register.yamlio import load_yaml
from aca.vaguelaw.backend import DecisionBackend
from aca.vaguelaw.classify import ASK, classify
from aca.vaguelaw.questions import load_questions

_CASES_DIR = Path(__file__).resolve().parents[3] / "eval" / "vaguelaw"
_RESULTS_DIR = Path(__file__).resolve().parents[3] / "eval" / "results"

SMOKE_NOTE = ("smoke only (FakeBackend or offline hashed LocalBackend); real accuracy/ECE "
              "to be measured by the owner with the trained model")
MODEL_NOTE = "measured with the trained model backend"


@dataclass
class EvalResult:
    n: int
    accuracy: float | None
    ece: float | None
    ask_rate: float | None
    by_question: dict = field(default_factory=dict)
    note: str = SMOKE_NOTE
    backend: str = ""
    is_smoke: bool = True


def load_cases(cases_dir: Path | None = None) -> list[dict]:
    base = cases_dir or _CASES_DIR
    if not base.exists():
        return []
    return [load_yaml(p) for p in sorted(base.glob("*.yaml"))]


def _ece(pairs: list[tuple[float, bool]], *, bins: int = 10) -> float | None:
    """Expected calibration error over p(yes) vs the correct label."""
    if not pairs:
        return None
    total = len(pairs)
    err = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        bucket = [(p, y) for p, y in pairs if (p > lo or (b == 0 and p == 0.0)) and p <= hi]
        if not bucket:
            continue
        conf = sum(p for p, _ in bucket) / len(bucket)
        acc = sum(1 for _, y in bucket if y) / len(bucket)
        err += (len(bucket) / total) * abs(conf - acc)
    return round(err, 4)


def evaluate(backend: DecisionBackend, *, cases_dir: Path | None = None) -> EvalResult:
    cases = load_cases(cases_dir)
    questions = {q.id: q for q in load_questions()}
    if not cases:
        return EvalResult(n=0, accuracy=None, ece=None, ask_rate=None)

    correct = 0
    scored = 0
    asks = 0
    cal_pairs: list[tuple[float, bool]] = []
    by_q: dict = {}

    for case in cases:
        qid = case["question_id"]
        q = questions.get(qid)
        if q is None:
            continue
        expect = bool(case["expect_yes"])
        routing = classify(case["state"], [q], backend)[0]
        qstat = by_q.setdefault(qid, {"n": 0, "correct": 0, "ask": 0, "scored": 0,
                                      "_cal": []})
        qstat["n"] += 1
        # p(yes) for calibration (routing carries it).
        cal_pairs.append((routing.p_yes, expect))
        qstat["_cal"].append((routing.p_yes, expect))
        if routing.route == ASK:
            asks += 1
            qstat["ask"] += 1
            continue  # ASK is neither right nor wrong; excluded from accuracy
        scored += 1
        qstat["scored"] += 1
        predicted_yes = routing.route == "ACT"
        if predicted_yes == expect:
            correct += 1
            qstat["correct"] += 1

    # Precompute per-question accuracy / ECE / ASK-rate, then drop the raw pairs.
    for qid, s in by_q.items():
        s["accuracy"] = round(s["correct"] / s["scored"], 4) if s["scored"] else None
        s["ask_rate"] = round(s["ask"] / s["n"], 4) if s["n"] else None
        s["ece"] = _ece(s.pop("_cal"))

    accuracy = round(correct / scored, 4) if scored else None
    ask_rate = round(asks / len(cases), 4) if cases else None
    is_smoke, backend_name = _backend_is_smoke(backend)
    return EvalResult(
        n=len(cases),
        accuracy=accuracy,
        ece=_ece(cal_pairs),
        ask_rate=ask_rate,
        by_question=by_q,
        backend=backend_name,
        is_smoke=is_smoke,
        note=SMOKE_NOTE if is_smoke else MODEL_NOTE,
    )


def _backend_is_smoke(backend) -> tuple[bool, str]:
    """A run is 'smoke' with the fake backend or a hashed-embedder local backend."""
    name = getattr(backend, "name", backend.__class__.__name__)
    if name == "fake":
        return True, "fake"
    emb = getattr(backend, "_embedder", None)
    # Trigger lazy load if the local backend has not built its embedder yet.
    if emb is None and hasattr(backend, "_emb"):
        try:
            emb = backend._emb()
        except Exception:
            emb = None
    version = str(getattr(emb, "version", "")) if emb is not None else ""
    is_hashed = not version.startswith("st:")
    return is_hashed, f"{name}:{version}" if version else name


def write_report(result: EvalResult, *, results_dir: Path | None = None) -> Path:
    import json
    import time

    base = results_dir or _RESULTS_DIR
    base.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    tag = "smoke" if result.is_smoke else "model"
    path = base / f"vaguelaw-eval-{stamp}-{tag}.json"
    payload = {
        "schema": "vaguelaw-eval/v1",
        "generated_ts": time.time(),
        "backend": result.backend,
        "is_smoke": result.is_smoke,
        "note": result.note,
        "n": result.n,
        "accuracy": result.accuracy,
        "ece": result.ece,
        "ask_rate": result.ask_rate,
        "by_question": result.by_question,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _make_backend(name: str, *, require_model: bool | None = None):
    if name == "fake":
        from aca.vaguelaw.fake_backend import FakeBackend
        return FakeBackend()
    if name == "local":
        from aca.vaguelaw.local_backend import LocalBackend
        return LocalBackend(require_model=require_model)
    raise SystemExit(f"unknown backend {name!r}; choose local or fake")


def run(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="python -m aca.vaguelaw.eval",
                                description="Evaluate the vague-law classifier (accuracy, ECE, ASK rate).")
    p.add_argument("--backend", choices=["local", "fake"], default="local",
                   help="local = open-source MiniLM/hashed backend; fake = deterministic (default local)")
    p.add_argument("--require-model", action="store_true",
                   help="fail loudly if the real sentence-transformers model is not available "
                        "(local backend only; also via ACA_REQUIRE_MODEL=1)")
    p.add_argument("--no-write", action="store_true", help="do not write a result JSON")
    args = p.parse_args(argv)

    backend = _make_backend(args.backend, require_model=True if args.require_model else None)
    result = evaluate(backend)

    acc = result.accuracy if result.accuracy is not None else "n/a"
    ece = result.ece if result.ece is not None else "n/a"
    ask = result.ask_rate if result.ask_rate is not None else "n/a"
    print("Vague-law classifier eval")
    print(f"  backend : {result.backend}")
    print(f"  cases   : {result.n}")
    print(f"  accuracy: {acc}   ECE: {ece}   ASK-rate: {ask}")
    if result.is_smoke:
        print(f"  note    : {result.note}")
    else:
        print(f"  note    : {result.note}")
    if not args.no_write:
        path = write_report(result)
        print(f"  written : {path}")
    return 0


def main() -> int:  # pragma: no cover - CLI glue
    import sys
    return run(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
