"""Tests for the revision-aware parquet cache."""
from __future__ import annotations

from datetime import date

import pandas as pd
from hypothesis import given
from hypothesis import strategies as st

from unemployment_pipeline.cache import ParquetCache
from unemployment_pipeline.config import Program, Seasonal, SeriesSpec


def _obs(series_id: str, dates: list[str], values: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "series_id": series_id,
        "year": [pd.Timestamp(d).year for d in dates],
        "period": [f"M{pd.Timestamp(d).month:02d}" for d in dates],
        "date": [pd.Timestamp(d) for d in dates],
        "value": values,
        "footnotes": "",
    })


def _spec(sid: str) -> SeriesSpec:
    return SeriesSpec(sid, Program.CPS, sid, Seasonal.SA, 1948)


def test_load_empty_returns_typed_columns(tmp_path) -> None:
    cache = ParquetCache(tmp_path)
    df = cache.load()
    assert df.empty
    assert {"series_id", "date", "value", "latest_flag"} <= set(df.columns)


def test_write_then_load_roundtrip(tmp_path) -> None:
    cache = ParquetCache(tmp_path)
    df = _obs("LNS14000000", ["2025-11-30", "2025-12-31"], [4.3, 4.4])
    cache.write(df)
    loaded = cache.load()
    assert len(loaded) == 2
    # latest_flag set on the most recent date
    latest = loaded[loaded["latest_flag"]]
    assert len(latest) == 1
    assert latest.iloc[0]["date"] == pd.Timestamp("2025-12-31")


def test_merge_dedupes_keeping_new_value(tmp_path) -> None:
    old = _obs("S1", ["2025-11-30", "2025-12-31"], [4.3, 4.4])
    new = _obs("S1", ["2025-12-31", "2026-01-31"], [4.5, 4.6])  # Dec revised 4.4 -> 4.5
    merged = ParquetCache.merge(old, new)
    dec = merged[(merged["series_id"] == "S1") & (merged["date"] == pd.Timestamp("2025-12-31"))]
    assert len(dec) == 1
    assert dec.iloc[0]["value"] == 4.5  # newest fetch wins
    assert len(merged) == 3  # Nov, Dec(revised), Jan


def test_refetch_start_year_subtracts_revision_window(tmp_path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write(_obs("S1", ["2026-04-30"], [4.0]))
    # 14-month window back from Apr 2026 -> Feb 2025
    assert cache.refetch_start_year(14, today=date(2026, 6, 1)) == 2025
    empty = ParquetCache(tmp_path / "empty")
    assert empty.refetch_start_year(14, today=date(2026, 6, 1)) is None


def test_split_specs_cold_vs_warm(tmp_path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write(_obs("WARM", ["2025-12-31"], [1.0]))
    cold, warm = cache.split_specs([_spec("WARM"), _spec("COLD")])
    assert [s.series_id for s in cold] == ["COLD"]
    assert [s.series_id for s in warm] == ["WARM"]


@given(
    n_old=st.integers(0, 5),
    n_overlap=st.integers(0, 5),
)
def test_merge_no_duplicate_keys(n_old: int, n_overlap: int) -> None:
    base = pd.Timestamp("2025-01-31")
    old_dates = [(base + pd.offsets.MonthEnd(i)).strftime("%Y-%m-%d") for i in range(n_old)]
    new_dates = [(base + pd.offsets.MonthEnd(i)).strftime("%Y-%m-%d")
                 for i in range(max(0, n_old - n_overlap), n_old + 2)]
    old = _obs("S1", old_dates, [1.0] * len(old_dates)) if old_dates else _obs("S1", ["2025-01-31"], [1.0]).iloc[0:0]
    new = _obs("S1", new_dates, [2.0] * len(new_dates))
    merged = ParquetCache.merge(old, new)
    keys = list(zip(merged["series_id"], merged["date"]))
    assert len(keys) == len(set(keys))
