"""Tests for the data-quality gate."""
from __future__ import annotations

import json
from datetime import date

import pandas as pd

from unemployment_pipeline.quality import run_quality_checks


def _obs(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame({
        "series_id": [r[0] for r in rows],
        "date": [pd.Timestamp(r[1]) for r in rows],
        "value": [r[2] for r in rows],
        "latest_flag": [True for _ in rows],
    })


def test_missing_required_core_fails() -> None:
    obs = _obs([("LNS14000000", "2026-04-30", 4.4)])
    report = run_quality_checks(obs, required_core={"LNS14000000", "LNS14027662"},
                                today=date(2026, 6, 1))
    assert report.passed is False
    cov = [r for r in report.results if r.name == "coverage_required_core"][0]
    assert "LNS14027662" in cov.detail


def test_all_required_present_passes() -> None:
    obs = _obs([("LNS14000000", "2026-04-30", 4.4), ("LNS14027662", "2026-04-30", 2.5)])
    report = run_quality_checks(obs, required_core={"LNS14000000", "LNS14027662"},
                                today=date(2026, 6, 1))
    assert report.passed is True


def test_jolts_identity_violation_flagged() -> None:
    # TS should equal QU + LD + OS = 5 + 3 + 2 = 10; inject TS = 12 (violation)
    obs = _obs([
        ("JTS000000000000000TSL", "2026-04-30", 12.0),
        ("JTS000000000000000QUL", "2026-04-30", 5.0),
        ("JTS000000000000000LDL", "2026-04-30", 3.0),
        ("JTS000000000000000OSL", "2026-04-30", 2.0),
    ])
    report = run_quality_checks(obs, required_core=set(), today=date(2026, 6, 1))
    identity = [r for r in report.results if r.name == "jolts_separations_identity"][0]
    assert identity.passed is False


def test_jolts_identity_holds() -> None:
    obs = _obs([
        ("JTS000000000000000TSL", "2026-04-30", 10.0),
        ("JTS000000000000000QUL", "2026-04-30", 5.0),
        ("JTS000000000000000LDL", "2026-04-30", 3.0),
        ("JTS000000000000000OSL", "2026-04-30", 2.0),
    ])
    report = run_quality_checks(obs, required_core=set(), today=date(2026, 6, 1))
    identity = [r for r in report.results if r.name == "jolts_separations_identity"][0]
    assert identity.passed is True


def test_report_serializes() -> None:
    obs = _obs([("LNS14000000", "2026-04-30", 4.4)])
    report = run_quality_checks(obs, required_core={"LNS14000000"}, today=date(2026, 6, 1))
    md = report.to_markdown()
    assert "Data-Quality Report" in md
    parsed = json.loads(report.to_json())
    assert "passed" in parsed and "results" in parsed
