"""Tests for the expanded-data analytics prepare functions."""
from __future__ import annotations

import pandas as pd
import pytest

from dashboard.prepare import (
    education_distribution,
    industry_employment_change,
    jolts_industry_change,
)


def _meta(rows: list[dict]) -> pd.DataFrame:
    cols = ["series_id", "program", "label", "geo_level", "measure",
            "education", "industry_naics"]
    return pd.DataFrame([{c: r.get(c) for c in cols} for r in rows])


def _obs(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame({
        "series_id": [r[0] for r in rows],
        "date": [pd.Timestamp(r[1]) for r in rows],
        "value": [r[2] for r in rows],
    })


def test_industry_employment_change_ranks_by_change_since_chatgpt() -> None:
    meta = _meta([
        {"series_id": "CESA", "program": "CES", "label": "Information",
         "geo_level": "national", "measure": "ces_01"},
        {"series_id": "CESB", "program": "CES", "label": "Construction",
         "geo_level": "national", "measure": "ces_01"},
    ])
    obs = _obs([
        ("CESA", "2022-11-30", 100.0), ("CESA", "2023-11-30", 110.0), ("CESA", "2024-11-30", 121.0),
        ("CESB", "2022-11-30", 200.0), ("CESB", "2023-11-30", 180.0), ("CESB", "2024-11-30", 171.0),
    ])
    out = industry_employment_change(obs, meta)
    a = out.set_index("label").loc["Information"]
    b = out.set_index("label").loc["Construction"]
    assert a["chg_since_chatgpt_pct"] == pytest.approx(21.0)
    assert a["chg_yoy_pct"] == pytest.approx(10.0)
    assert b["chg_since_chatgpt_pct"] == pytest.approx(-14.5)
    # ranked descending by change since ChatGPT
    assert list(out["label"]) == ["Information", "Construction"]


def test_education_distribution_computes_shares() -> None:
    meta = _meta([
        {"series_id": "EMP_B", "program": "CES", "label": "x"},  # noise (wrong program)
        {"series_id": "E_BACH", "program": "CPS", "label": "Bach emp",
         "measure": "employment_level", "education": "bachelors_plus"},
        {"series_id": "E_HS", "program": "CPS", "label": "HS emp",
         "measure": "employment_level", "education": "high_school"},
    ])
    obs = _obs([
        ("E_BACH", "2026-04-30", 60000.0),
        ("E_HS", "2026-04-30", 40000.0),
    ])
    dist = education_distribution(obs, meta)
    latest = dist[dist["date"] == dist["date"].max()].set_index("education")
    assert latest.loc["bachelors_plus", "share"] == pytest.approx(0.60)
    assert latest.loc["high_school", "share"] == pytest.approx(0.40)


def test_jolts_industry_change_openings() -> None:
    meta = _meta([
        {"series_id": "JO_INFO", "program": "JOLTS", "label": "Information",
         "measure": "jolts_job_openings_level"},
        {"series_id": "JO_CONS", "program": "JOLTS", "label": "Construction",
         "measure": "jolts_job_openings_level"},
    ])
    obs = _obs([
        ("JO_INFO", "2022-11-30", 200.0), ("JO_INFO", "2024-11-30", 100.0),
        ("JO_CONS", "2022-11-30", 300.0), ("JO_CONS", "2024-11-30", 330.0),
    ])
    out = jolts_industry_change(obs, meta)
    info = out.set_index("label").loc["Information"]
    assert info["openings_chg_since_chatgpt_pct"] == pytest.approx(-50.0)
    # most negative first
    assert list(out["label"])[0] == "Information"
