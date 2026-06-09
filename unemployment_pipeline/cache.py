"""Delta + revision-aware parquet cache for BLS observations."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from unemployment_pipeline.config import SeriesSpec

_COLUMNS = ["series_id", "year", "period", "date", "value", "footnotes", "latest_flag"]


class ParquetCache:
    """Stores the long observations frame and merges new fetches into it."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.obs_path = self.cache_dir / "observations.parquet"

    def load(self) -> pd.DataFrame:
        if not self.obs_path.exists():
            return pd.DataFrame({c: pd.Series(dtype=_dtype(c)) for c in _COLUMNS})
        return pd.read_parquet(self.obs_path)

    def write(self, df: pd.DataFrame) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        out = _set_latest_flag(df).sort_values(["series_id", "date"]).reset_index(drop=True)
        out.to_parquet(self.obs_path, index=False)

    @staticmethod
    def merge(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
        """Concat; on duplicate (series_id, date) keep the newest (``new``) row."""
        combined = pd.concat([old, new], ignore_index=True)
        combined = combined.drop_duplicates(subset=["series_id", "date"], keep="last")
        combined = _set_latest_flag(combined)
        return combined.sort_values(["series_id", "date"]).reset_index(drop=True)

    def refetch_start_year(self, revision_months: int, today: Optional[date] = None) -> Optional[int]:
        """Year to start the trailing refetch window from; None if cache empty."""
        df = self.load()
        if df.empty:
            return None
        max_date = pd.Timestamp(df["date"].max())
        start = max_date - pd.DateOffset(months=revision_months)
        return int(start.year)

    def split_specs(
        self, specs: Sequence[SeriesSpec]
    ) -> tuple[list[SeriesSpec], list[SeriesSpec]]:
        """Partition specs into (cold = never cached, warm = already cached)."""
        cached = set(self.load()["series_id"].unique())
        cold = [s for s in specs if s.series_id not in cached]
        warm = [s for s in specs if s.series_id in cached]
        return cold, warm


def _dtype(column: str) -> str:
    if column == "value":
        return "float64"
    if column == "year":
        return "int64"
    if column == "date":
        return "datetime64[ns]"
    if column == "latest_flag":
        return "bool"
    return "object"


def _set_latest_flag(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if df.empty:
        df["latest_flag"] = pd.Series(dtype="bool")
        return df
    idx_latest = df.groupby("series_id")["date"].transform("max")
    df["latest_flag"] = df["date"] == idx_latest
    return df
