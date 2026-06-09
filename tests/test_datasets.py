"""Tests for the tidy dataset output contract."""
from __future__ import annotations

import pandas as pd
import pandas.testing as pdt

from unemployment_pipeline.config import Program, Seasonal, SeriesSpec
from unemployment_pipeline.datasets import read_dataset, specs_to_meta, write_datasets


def _specs() -> list[SeriesSpec]:
    return [
        SeriesSpec("LNS14000000", Program.CPS, "UR", Seasonal.SA, 1948,
                   measure="unemployment_rate", unit="percent"),
        SeriesSpec("OEUN000000000000150000­01".replace("­", ""), Program.OEWS,
                   "Comp & Math emp", Seasonal.NSA, 2014, occupation_soc="150000",
                   measure="oews_01", annual_only=True),
    ]


def _obs() -> pd.DataFrame:
    return pd.DataFrame({
        "series_id": ["LNS14000000", "LNS14000000"],
        "year": [2025, 2025],
        "period": ["M11", "M12"],
        "date": [pd.Timestamp("2025-11-30"), pd.Timestamp("2025-12-31")],
        "value": [4.3, 4.4],
        "footnotes": ["", ""],
        "latest_flag": [False, True],
    })


def test_specs_to_meta_one_row_each_with_string_enums() -> None:
    meta = specs_to_meta(_specs())
    assert len(meta) == 2
    assert set(meta.columns) >= {
        "series_id", "program", "label", "seasonal", "geo_level",
        "occupation_soc", "measure", "history_start_year", "annual_only",
    }
    row = meta.set_index("series_id").loc["LNS14000000"]
    assert row["program"] == "CPS"      # enum rendered as name string
    assert row["seasonal"] == "SA"


def test_write_and_read_datasets_roundtrip(tmp_path) -> None:
    exp_occ = pd.DataFrame({"soc6": ["150000"], "aioe": [1.1], "gpts_beta": [0.5]})
    exp_ind = pd.DataFrame({"naics": ["51"], "aiie": [0.8]})
    write_datasets(_obs(), _specs(), exp_occ, exp_ind, tmp_path)
    for name in ("observations", "series_meta", "exposure_occupation", "exposure_industry"):
        assert (tmp_path / f"{name}.parquet").exists()
    obs_back = read_dataset("observations", tmp_path)
    assert len(obs_back) == 2
    pdt.assert_frame_equal(
        read_dataset("exposure_industry", tmp_path).reset_index(drop=True), exp_ind
    )


def test_write_is_deterministic(tmp_path) -> None:
    write_datasets(_obs(), _specs(), pd.DataFrame({"soc6": []}),
                   pd.DataFrame({"naics": []}), tmp_path)
    first = read_dataset("series_meta", tmp_path)
    write_datasets(_obs(), _specs(), pd.DataFrame({"soc6": []}),
                   pd.DataFrame({"naics": []}), tmp_path)
    second = read_dataset("series_meta", tmp_path)
    pdt.assert_frame_equal(first, second)
