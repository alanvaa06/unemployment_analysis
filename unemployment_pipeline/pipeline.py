"""Top-level orchestration: registry -> fetch -> cache -> datasets -> quality."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional, Set

import pandas as pd

from unemployment_pipeline.bls_client import HttpPoster, RequestsHttpPoster, fetch_series
from unemployment_pipeline.cache import ParquetCache
from unemployment_pipeline.config import FetchConfig, Program
from unemployment_pipeline.datasets import read_dataset, write_datasets
from unemployment_pipeline.exposure import (
    build_exposure_occupation,
    load_aiie,
    load_aioe,
    load_gpts,
)
from unemployment_pipeline.programs.constants import AI_SOC
from unemployment_pipeline.quality import DEFAULT_REQUIRED_CORE, QualityReport, run_quality_checks
from unemployment_pipeline.registry import build_registry

_OCC_COLS = ["soc6", "gpts_alpha", "gpts_beta", "gpts_gamma", "aioe", "aioe_langmod"]
_IND_COLS = ["naics", "aiie", "aiie_langmod"]


def load_exposure_tables(reference_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build occupation/industry exposure tables from cached reference files.

    Returns empty (typed) frames when the reference files are absent.
    """
    reference_dir = Path(reference_dir)
    gpts_path = reference_dir / "gpts_occ_level.csv"
    aioe_path = reference_dir / "aioe.xlsx"
    aioe_lang_path = reference_dir / "aioe_langmod.xlsx"
    soc_list = [soc for soc, _, _ in AI_SOC]

    if gpts_path.exists() and aioe_path.exists():
        gpts = load_gpts(gpts_path)
        aioe = load_aioe(aioe_path, aioe_lang_path if aioe_lang_path.exists() else None)
        occ, _unmatched = build_exposure_occupation(soc_list, gpts, aioe)
    else:
        occ = pd.DataFrame(columns=_OCC_COLS)

    if aioe_path.exists():
        try:
            ind = load_aiie(aioe_path)
        except ValueError:
            ind = pd.DataFrame(columns=_IND_COLS)
    else:
        ind = pd.DataFrame(columns=_IND_COLS)
    return occ, ind


def fetch_all(
    config: FetchConfig,
    http: Optional[HttpPoster] = None,
    current_year: Optional[int] = None,
    today: Optional[date] = None,
    required_core: Optional[Set[str]] = None,
) -> QualityReport:
    """Run the full pipeline; returns the quality report and writes all outputs."""
    if http is None:
        http = RequestsHttpPoster()

    specs = build_registry(config)
    cache = ParquetCache(config.cache_dir)
    cold, warm = cache.split_specs(specs)

    frames: list[pd.DataFrame] = []
    if cold:
        df_cold, _ = fetch_series(cold, config, http, current_year=current_year)
        frames.append(df_cold)
    if warm:
        start = cache.refetch_start_year(config.revision_refetch_months, today)
        df_warm, _ = fetch_series(
            warm, config, http, current_year=current_year, start_year_override=start
        )
        frames.append(df_warm)

    new = pd.concat(frames, ignore_index=True) if frames else cache.load().iloc[0:0]
    merged = cache.merge(cache.load(), new)
    cache.write(merged)

    occ, ind = load_exposure_tables(config.reference_dir)
    write_datasets(merged, specs, occ, ind, config.cache_dir)

    requested = {s.series_id for s in specs}
    core = (required_core if required_core is not None else DEFAULT_REQUIRED_CORE) & requested
    report = run_quality_checks(merged, required_core=core, today=today)

    config.quality_dir.mkdir(parents=True, exist_ok=True)
    (config.quality_dir / "quality_report.md").write_text(report.to_markdown(), encoding="utf-8")
    (config.quality_dir / "quality_report.json").write_text(report.to_json(), encoding="utf-8")
    return report


def load_dataset(name: str, cache_dir: Path = Path("data/cache")) -> pd.DataFrame:
    """Read one of the output-contract tables (observations, series_meta, ...)."""
    return read_dataset(name, cache_dir)
