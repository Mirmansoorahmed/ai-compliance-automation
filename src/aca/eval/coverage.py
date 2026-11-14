"""Requirement coverage report (R11.3, R11.4).

Computes, over the in-scope requirement set:
  % mapped  — requirements with status active (counted as in the register)
  % auto / % human / % hybrid — share by mode

A configurable floor fails the coverage job when the mapped share is below it.
The floor is a TARGET (a design budget), not a measured result; it is set in
``coverage_floor.json`` and can be tightened once the starter map is stable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aca.register.yamlio import load_yaml

_REPO = Path(__file__).resolve().parents[3]
_REQ_DIR = _REPO / "requirements"
_FLOOR_FILE = _REPO / "eval" / "coverage_floor.json"


@dataclass
class CoverageReport:
    total: int
    mapped: int
    by_mode: dict
    pct_mapped: float
    pct_auto: float
    pct_human: float
    pct_hybrid: float
    floor: float | None

    @property
    def passes_floor(self) -> bool:
        return self.floor is None or self.pct_mapped >= self.floor

    def to_dict(self) -> dict:
        return {
            "schema": "coverage-report/v1",
            "total": self.total,
            "mapped": self.mapped,
            "by_mode": self.by_mode,
            "pct_mapped": self.pct_mapped,
            "pct_auto": self.pct_auto,
            "pct_human": self.pct_human,
            "pct_hybrid": self.pct_hybrid,
            "floor": self.floor,
            "floor_note": "TARGET (design budget), not a measured result",
            "passes_floor": self.passes_floor,
        }


def _load_floor(floor_file: Path | None) -> float | None:
    path = floor_file or _FLOOR_FILE
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("pct_mapped_floor")


def compute_coverage(
    requirements_dir: Path | None = None,
    *,
    floor_file: Path | None = None,
) -> CoverageReport:
    req_dir = requirements_dir or _REQ_DIR
    reqs = [load_yaml(p) for p in sorted(req_dir.glob("*.yaml"))]
    total = len(reqs)
    mapped = sum(1 for r in reqs if r.get("status") == "active")
    modes = {"auto": 0, "human": 0, "hybrid": 0}
    for r in reqs:
        m = r.get("mode")
        if m in modes:
            modes[m] += 1

    def pct(n: int) -> float:
        return round(100.0 * n / total, 2) if total else 0.0

    return CoverageReport(
        total=total,
        mapped=mapped,
        by_mode=modes,
        pct_mapped=pct(mapped),
        pct_auto=pct(modes["auto"]),
        pct_human=pct(modes["human"]),
        pct_hybrid=pct(modes["hybrid"]),
        floor=_load_floor(floor_file),
    )


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI glue
    report = compute_coverage()
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    if not report.passes_floor:
        print(f"coverage below floor {report.floor}% (mapped {report.pct_mapped}%)")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
