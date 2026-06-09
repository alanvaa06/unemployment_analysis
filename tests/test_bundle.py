"""Tests for the interactive data-bundle builders."""
from __future__ import annotations

import pandas as pd
import pytest

from dashboard.bundle import (
    change_since,
    monthly_industry_bundle,
    state_ur_by_year,
)


def _meta(rows: list[dict]) -> pd.DataFrame:
    cols = ["series_id", "program", "label", "geo_level", "measure", "seasonal",
            "education", "industry_naics"]
    return pd.DataFrame([{c: r.get(c) for c in cols} for r in rows])


def _obs(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame({
        "series_id": [r[0] for r in rows],
        "date": [pd.Timestamp(r[1]) for r in rows],
        "value": [r[2] for r in rows],
    })


def test_change_since_uses_last_on_or_before_baseline() -> None:
    dates = ["2021-03", "2022-12", "2026-05"]
    values = [100.0, 110.0, 121.0]
    assert change_since(dates, values, "2022-12", "2026-05") == pytest.approx(10.0)
    assert change_since(dates, values, "2021-03", "2026-05") == pytest.approx(21.0)
    # baseline between points -> last on/before
    assert change_since(dates, values, "2022-01", "2026-05") == pytest.approx(21.0)
    # missing -> None
    assert change_since(dates, values, "2019-01", "2026-05") is None


def test_monthly_industry_bundle_shape_and_filtering() -> None:
    meta = _meta([
        {"series_id": "CES5000000001", "program": "CES", "label": "Information: all employees (000s)",
         "geo_level": "national", "measure": "ces_01", "seasonal": "SA"},
        {"series_id": "CEU5000000001", "program": "CES", "label": "Information NSA",
         "geo_level": "national", "measure": "ces_01", "seasonal": "NSA"},  # excluded (NSA)
        {"series_id": "CES0000000001", "program": "CES", "label": "Total nonfarm",
         "geo_level": "national", "measure": "ces_01", "seasonal": "SA"},   # excluded (aggregate)
    ])
    obs = _obs([
        ("CES5000000001", "2022-11-30", 3000.0), ("CES5000000001", "2026-05-31", 2680.0),
        ("CEU5000000001", "2022-11-30", 3010.0),
        ("CES0000000001", "2022-11-30", 155000.0),
    ])
    bundle = monthly_industry_bundle(obs, meta)
    keys = {b["key"] for b in bundle}
    assert "CES5000000001" in keys
    assert "CEU5000000001" not in keys      # NSA dropped
    assert "CES0000000001" not in keys      # aggregate dropped
    info = [b for b in bundle if b["key"] == "CES5000000001"][0]
    assert info["label"] == "Information"
    assert info["dates"] == ["2022-11", "2026-05"]
    assert info["values"] == [3000.0, 2680.0]


def test_state_ur_by_year_annual_average() -> None:
    obs = _obs([
        ("LASST060000000000003", "2025-01-31", 5.0),
        ("LASST060000000000003", "2025-07-31", 5.4),   # CA 2025 avg 5.2
        ("LASST480000000000003", "2025-01-31", 4.0),
    ])
    out = state_ur_by_year(obs)
    ca = out[(out["abbr"] == "CA") & (out["year"] == 2025)]["ur"].iloc[0]
    assert ca == pytest.approx(5.2)
    assert set(out["abbr"]) == {"CA", "TX"}
