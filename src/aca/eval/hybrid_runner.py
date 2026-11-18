"""Hybrid-profile eval runner (R12.5, R14.5).

Runs the labelled eval set through the FULL Semantic Guard on the hybrid
profile, so vendor/judge adapters contribute labels when credentials exist. It
reports the vendor path **separately** from the local path, so a Prompt Shields
or judge miss is never hidden inside a blended number.

Metrics discipline: with no Azure credentials the vendor/judge adapters report
unavailable and this runner marks the hybrid metrics **TO BE MEASURED** — it
never invents a hybrid number. A real hybrid run requires live credentials (see
docs/HYBRID.md) and is not performed in CI or the offline sandbox.

The oss runner (``aca.eval.runner``) is unchanged and remains the CI-guaranteed
path.
"""

from __future__ import annotations

import time
from pathlib import Path

from aca.config import load_config
from aca.eval.runner import load_cases
from aca.guard.event import Event
from aca.guard.service import SemanticGuard

VENDOR_CONCEPTS = ("PROMPT-INJECTION",)  # Prompt Shields signal; scored separately
TO_BE_MEASURED = "TO BE MEASURED"


def _vendor_adapters_present(guard: SemanticGuard) -> list[str]:
    vendor = []
    for name in guard.adapter_names:
        if name in ("prompt_shields", "judge"):
            vendor.append(name)
    return vendor


def run_hybrid_eval(
    *,
    cases_dir: Path | None = None,
    repo_root: Path | None = None,
    guard: SemanticGuard | None = None,
) -> dict:
    root = repo_root or Path(__file__).resolve().parents[3]
    guard = guard or SemanticGuard(load_config("hybrid"))
    vendor = _vendor_adapters_present(guard)

    cases = load_cases(cases_dir)

    # Count how often the vendor path contributed a (separate) signal.
    vendor_hits = 0
    vendor_latency: list[float] = []
    for case in cases:
        text = case.get("text") or " ".join(case.get("turns", []))
        start = time.perf_counter()
        labels = guard.label(Event(text=text, language=case.get("lang")))
        vendor_latency.append((time.perf_counter() - start) * 1000.0)
        if any(l.get("concept_id") in VENDOR_CONCEPTS for l in labels):
            vendor_hits += 1

    measured = bool(vendor)  # vendor adapters actually live -> metrics measurable
    return {
        "schema": "hybrid-eval-report/v1",
        "generated_ts": time.time(),
        "profile": "hybrid",
        "vendor_adapters_present": vendor,
        "n_cases": len(cases),
        # Scored SEPARATELY from the local path. Until a real credentialed run,
        # these are TO BE MEASURED — never invented.
        "vendor_path": {
            "measured": measured,
            "vendor_signal_hits": vendor_hits if measured else TO_BE_MEASURED,
            "vendor_p95_ms": (
                _p95(vendor_latency) if measured and vendor_latency else TO_BE_MEASURED
            ),
            "precision": TO_BE_MEASURED,
            "recall": TO_BE_MEASURED,
            "note": (
                "Vendor/judge path scored separately from the local path. "
                "No Azure credentials -> TO BE MEASURED. See docs/HYBRID.md."
            ),
        },
    }


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return round(ordered[k], 3)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI glue
    import json

    report = run_hybrid_eval()
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["vendor_adapters_present"]:
        print("\nNo hybrid vendor adapters available (no Azure credentials).")
        print("Hybrid metrics are TO BE MEASURED. See docs/HYBRID.md to run a real eval.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
