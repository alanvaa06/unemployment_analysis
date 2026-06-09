"""Assemble and persist the tidy output contract (Phase-2 dashboard input)."""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Sequence

import pandas as pd

from unemployment_pipeline.config import SeriesSpec

_META_FIELDS = [
    "series_id", "program", "label", "seasonal", "history_start_year",
    "geo_level", "geo_code", "geo_name", "industry_naics", "occupation_soc",
    "education", "demographic", "measure", "unit", "annual_only",
]


def specs_to_meta(specs: Sequence[SeriesSpec]) -> pd.DataFrame:
    """One row per series with enums rendered as their name strings."""
    rows = []
    for spec in specs:
        d = dataclasses.asdict(spec)
        d["program"] = spec.program.name
        d["seasonal"] = spec.seasonal.name
        rows.append({field: d.get(field) for field in _META_FIELDS})
    return pd.DataFrame(rows, columns=_META_FIELDS).sort_values("series_id").reset_index(drop=True)


def write_datasets(
    observations: pd.DataFrame,
    specs: Sequence[SeriesSpec],
    exposure_occupation: pd.DataFrame,
    exposure_industry: pd.DataFrame,
    out_dir: Path,
) -> None:
    """Write the four parquet tables, sorted for determinism."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    obs = observations.copy()
    if not obs.empty:
        obs = obs.sort_values(["series_id", "date"]).reset_index(drop=True)
    obs.to_parquet(out_dir / "observations.parquet", index=False)

    specs_to_meta(specs).to_parquet(out_dir / "series_meta.parquet", index=False)
    exposure_occupation.reset_index(drop=True).to_parquet(
        out_dir / "exposure_occupation.parquet", index=False)
    exposure_industry.reset_index(drop=True).to_parquet(
        out_dir / "exposure_industry.parquet", index=False)


def read_dataset(name: str, out_dir: Path) -> pd.DataFrame:
    """Read one of the contract tables by name."""
    return pd.read_parquet(Path(out_dir) / f"{name}.parquet")
