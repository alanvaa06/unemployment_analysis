"""Tests for SOC crosswalk + AI-exposure index joins."""
from __future__ import annotations

import pandas as pd
import pytest

from unemployment_pipeline.crosswalks import onet_to_soc6
from unemployment_pipeline.exposure import (
    build_exposure_occupation,
    load_aioe,
    load_gpts,
)


@pytest.mark.parametrize("raw,expected", [
    ("15-1252.00", "151252"),
    ("15-1252", "151252"),
    ("151252", "151252"),
    ("43-9021.00", "439021"),
])
def test_onet_to_soc6(raw: str, expected: str) -> None:
    assert onet_to_soc6(raw) == expected


def test_load_gpts_collapses_onet_to_soc6(tmp_path) -> None:
    csv = tmp_path / "gpts.csv"
    pd.DataFrame({
        "onet_soc": ["15-1252.00", "15-1252.01", "27-3043.00"],
        "alpha": [0.4, 0.6, 0.8],
        "beta": [0.5, 0.7, 0.9],
        "gamma": [0.6, 0.8, 1.0],
    }).to_csv(csv, index=False)
    out = load_gpts(csv)
    soft = out.set_index("soc6")
    assert set(out.columns) >= {"soc6", "gpts_alpha", "gpts_beta", "gpts_gamma"}
    # two O*NET rows for 15-1252 collapse to one SOC6 via mean
    assert soft.loc["151252", "gpts_beta"] == pytest.approx(0.6)
    assert soft.loc["273043", "gpts_beta"] == pytest.approx(0.9)


def test_load_aioe_normalizes_soc(tmp_path) -> None:
    xlsx = tmp_path / "aioe.xlsx"
    pd.DataFrame({
        "SOC": ["15-1252", "27-3043"],
        "AIOE": [1.23, -0.45],
    }).to_excel(xlsx, index=False)
    out = load_aioe(xlsx)
    assert set(out.columns) >= {"soc6", "aioe"}
    assert out.set_index("soc6").loc["151252", "aioe"] == pytest.approx(1.23)


def test_build_exposure_occupation_reports_unmatched(tmp_path) -> None:
    gpts = pd.DataFrame({"soc6": ["151252"], "gpts_alpha": [0.4],
                         "gpts_beta": [0.5], "gpts_gamma": [0.6]})
    aioe = pd.DataFrame({"soc6": ["151252"], "aioe": [1.2], "aioe_langmod": [0.9]})
    joined, unmatched = build_exposure_occupation(["151252", "999999"], gpts, aioe)
    assert "999999" in unmatched
    row = joined.set_index("soc6").loc["151252"]
    assert row["gpts_beta"] == pytest.approx(0.5)
    assert row["aioe"] == pytest.approx(1.2)
