"""Data-quality gate: coverage, identities, freshness."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Optional, Set

import pandas as pd

# Series that MUST be present for the run to be considered trustworthy.
DEFAULT_REQUIRED_CORE: Set[str] = {
    "LNS14000000",  # unemployment rate
    "LNS14027659", "LNS14027660", "LNS14027689", "LNS14027662",  # education quartet
    "CES0000000001", "CES5000000001", "CES6000000001",  # total nonfarm, Info, PBS
    "JTS000000000000000JOL", "JTS000000000000000HIL",  # openings, hires
}

_JOLTS_TS = "JTS000000000000000TSL"
_JOLTS_QU = "JTS000000000000000QUL"
_JOLTS_LD = "JTS000000000000000LDL"
_JOLTS_OS = "JTS000000000000000OSL"


@dataclass
class CheckResult:
    name: str
    passed: bool
    severity: str  # "fail" | "warn" | "info"
    detail: str


@dataclass
class QualityReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results if r.severity == "fail")

    def to_json(self) -> str:
        return json.dumps(
            {"passed": self.passed, "results": [asdict(r) for r in self.results]},
            indent=2,
        )

    def to_markdown(self) -> str:
        lines = ["# Data-Quality Report", "",
                 f"**Overall: {'PASS' if self.passed else 'FAIL'}**", "",
                 "| Check | Severity | Status | Detail |",
                 "|---|---|---|---|"]
        for r in self.results:
            status = "✅" if r.passed else ("⚠️" if r.severity == "warn" else "❌")
            lines.append(f"| {r.name} | {r.severity} | {status} | {r.detail} |")
        return "\n".join(lines)


def _latest_value(obs: pd.DataFrame, series_id: str) -> Optional[float]:
    rows = obs[obs["series_id"] == series_id]
    if rows.empty:
        return None
    latest = rows.sort_values("date").iloc[-1]
    val = latest["value"]
    return None if pd.isna(val) else float(val)


def _check_coverage(obs: pd.DataFrame, required_core: Set[str]) -> CheckResult:
    present = set(obs["series_id"].unique())
    missing = sorted(required_core - present)
    return CheckResult(
        "coverage_required_core", not missing, "fail",
        "all present" if not missing else f"missing: {missing}",
    )


def _check_jolts_identity(obs: pd.DataFrame, rel_tol: float = 0.05) -> CheckResult:
    """TS ≈ QU + LD + OS. SA components are adjusted independently, so allow a
    relative tolerance rather than exact equality."""
    ts = _latest_value(obs, _JOLTS_TS)
    qu = _latest_value(obs, _JOLTS_QU)
    ld = _latest_value(obs, _JOLTS_LD)
    os_ = _latest_value(obs, _JOLTS_OS)
    if None in (ts, qu, ld, os_):
        return CheckResult("jolts_separations_identity", True, "warn",
                           "components not all present; skipped")
    diff = abs(ts - (qu + ld + os_))  # type: ignore[operator]
    rel = diff / max(abs(ts), 1.0)  # type: ignore[arg-type]
    return CheckResult(
        "jolts_separations_identity", rel <= rel_tol, "warn",
        f"|TS-(QU+LD+OS)| = {diff:.1f} ({rel:.1%}; tol {rel_tol:.0%})",
    )


_FRESHNESS_TOL_DAYS = {"LN": 75, "CE": 75, "LA": 75, "JT": 120}


def _check_freshness(obs: pd.DataFrame, today: date) -> CheckResult:
    if obs.empty:
        return CheckResult("freshness", True, "warn", "no observations")
    stale = []
    today_ts = pd.Timestamp(today)
    for prefix, tol in _FRESHNESS_TOL_DAYS.items():
        sub = obs[obs["series_id"].str.startswith(prefix)]
        if sub.empty:
            continue
        latest = pd.Timestamp(sub["date"].max())
        age = (today_ts - latest).days
        if age > tol:
            stale.append(f"{prefix}:{age}d")
    return CheckResult("freshness", not stale, "warn",
                       "fresh" if not stale else f"stale: {stale}")


def run_quality_checks(
    obs: pd.DataFrame,
    required_core: Optional[Set[str]] = None,
    today: Optional[date] = None,
) -> QualityReport:
    """Run all checks and return a report (``passed`` reflects fail-severity only)."""
    if required_core is None:
        required_core = DEFAULT_REQUIRED_CORE
    if today is None:
        today = date.today()
    results = [
        _check_coverage(obs, required_core),
        _check_jolts_identity(obs),
        _check_freshness(obs, today),
    ]
    return QualityReport(results)
