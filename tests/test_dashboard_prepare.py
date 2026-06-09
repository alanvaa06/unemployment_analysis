"""Tests for dashboard data-prep (pure functions over the parquet contract)."""
from __future__ import annotations

import pandas as pd
import pytest

from dashboard.prepare import (
    ai_sector_index,
    education_gradient,
    state_latest_ur,
    tightness_ratio,
)


def _long(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame({
        "series_id": [r[0] for r in rows],
        "date": [pd.Timestamp(r[1]) for r in rows],
        "value": [r[2] for r in rows],
    })


def test_education_gradient_builds_gap() -> None:
    obs = _long([
        ("LNS14027659", "2026-04-30", 6.0),   # less than HS
        ("LNS14027660", "2026-04-30", 4.0),   # high school
        ("LNS14027689", "2026-04-30", 3.0),   # some college
        ("LNS14027662", "2026-04-30", 2.0),   # bachelors+
    ])
    g = education_gradient(obs)
    row = g.iloc[0]
    assert row["bachelors_plus"] == 2.0
    assert row["less_than_hs"] == 6.0
    # gap = high_school - bachelors_plus (normally positive; narrowing = AI signal)
    assert row["gap_hs_minus_bach"] == pytest.approx(2.0)


def test_ai_sector_index_rebased_to_100_at_base() -> None:
    obs = _long([
        ("CES5000000001", "2022-11-30", 3000.0),  # Information at base
        ("CES5000000001", "2023-11-30", 2700.0),  # -10%
        ("CES0000000001", "2022-11-30", 155000.0),
        ("CES0000000001", "2023-11-30", 158100.0),  # +2%
    ])
    idx = ai_sector_index(obs, base_date="2022-11-30")
    info = idx.set_index("date")["Information"]
    assert info.loc[pd.Timestamp("2022-11-30")] == pytest.approx(100.0)
    assert info.loc[pd.Timestamp("2023-11-30")] == pytest.approx(90.0)
    total = idx.set_index("date")["Total nonfarm"]
    assert total.loc[pd.Timestamp("2023-11-30")] == pytest.approx(102.0)


def test_tightness_ratio_divides_unemployed_by_openings() -> None:
    obs = _long([
        ("LNS13000000", "2026-04-30", 7000.0),               # unemployed (000s)
        ("JTS000000000000000JOL", "2026-04-30", 7000.0),     # openings (000s)
        ("LNS13000000", "2026-03-31", 6000.0),
        ("JTS000000000000000JOL", "2026-03-31", 8000.0),
    ])
    t = tightness_ratio(obs).set_index("date")["ratio"]
    assert t.loc[pd.Timestamp("2026-04-30")] == pytest.approx(1.0)
    assert t.loc[pd.Timestamp("2026-03-31")] == pytest.approx(0.75)


def test_state_latest_ur_maps_fips_to_abbr() -> None:
    obs = _long([
        ("LASST060000000000003", "2026-03-31", 5.1),
        ("LASST060000000000003", "2026-04-30", 5.3),   # latest
        ("LASST480000000000003", "2026-04-30", 4.0),
    ])
    s = state_latest_ur(obs).set_index("abbr")
    assert s.loc["CA", "ur"] == 5.3
    assert s.loc["TX", "ur"] == 4.0
