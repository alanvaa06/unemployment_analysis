"""Export the analysis as a multi-sheet Excel workbook (one sheet per chart)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from dashboard import advanced, bundle, prepare
from unemployment_pipeline.datasets import read_dataset


def chart_frames(base: str = "2022-11", compare: str = "2026-05",
                 cache_dir: Path = Path("data/cache")) -> dict[str, pd.DataFrame]:
    """Return {sheet_name: DataFrame} of the underlying data behind each chart."""
    obs = prepare.load_observations(cache_dir)
    meta = read_dataset("series_meta", cache_dir)
    occ_exp = read_dataset("exposure_occupation", cache_dir)
    exp_ind = read_dataset("exposure_industry", cache_dir)
    frames: dict[str, pd.DataFrame] = {}

    k = prepare.national_kpis(obs)
    frames["KPIs"] = pd.DataFrame([{"metric": m, "value": v} for m, v in k.items()])
    frames["UnemploymentRate"] = prepare.ur_timeseries(obs)
    frames["EducationGradient"] = prepare.education_gradient(obs)
    frames["Waterfall"] = advanced.contribution_waterfall(obs, meta, base, compare)

    # detailed industry change (the beeswarm data)
    adv = advanced.advanced_bundle(obs, meta, exp_ind)
    rows = []
    for d in adv["detailed"]:
        pct = bundle.change_since(d["dates"], d["values"], base, compare)
        rows.append({"industry": d["label"], "naics": d["naics"], "aiie": d["aiie"],
                     "pct_change": pct, "employment_latest": d["values"][-1] if d["values"] else None})
    frames["IndustryChange"] = pd.DataFrame(rows).dropna(subset=["pct_change"]) \
        .sort_values("pct_change").reset_index(drop=True)

    frames["ExposureScatter"] = advanced.exposure_industry_change(obs, meta, exp_ind, base, compare)
    frames["EventStudy"] = advanced.event_study_indexed(obs, "2022-11", "CES5000000001", ["CES0500000001"])
    frames["FreezeVsCuts"] = advanced.freeze_vs_cuts(obs, meta, base, compare)

    m = bundle.industry_year_matrix(obs, meta, only_ids={s for s, _, _ in advanced.DISPLAY_INDUSTRIES})
    hm = pd.DataFrame(m["z"], index=m["industries"], columns=[str(y) for y in m["years"]])
    frames["IndustryYoY_Heatmap"] = hm.reset_index().rename(columns={"index": "industry"})

    frames["DiffusionIndex"] = advanced.diffusion_index(obs, window_months=6)
    frames["StateDispersion"] = advanced.state_ur_dispersion(obs)
    frames["ChangeDistribution"] = advanced.change_distribution(
        obs, [s for s, _, n in advanced.DISPLAY_INDUSTRIES if n in advanced._AI_NAICS],
        [s for s, _, n in advanced.LEAF_PARTITION if n not in advanced._AI_NAICS], "2023-01", 12)
    frames["StatesSwarm"] = advanced.state_ur_change_techshare(obs, base, compare)
    frames["Beveridge"] = advanced.beveridge_series(obs)
    frames["Occupations"] = prepare.occupation_exposure(obs, meta, occ_exp)
    return frames


def build_workbook(out_path: Path, base: str = "2022-11", compare: str = "2026-05",
                   cache_dir: Path = Path("data/cache")) -> Path:
    """Write one sheet per chart to an .xlsx workbook."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames = chart_frames(base, compare, cache_dir)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        readme = pd.DataFrame({
            "about": [
                "Has AI taken a toll on US jobs? — chart data export",
                f"baseline={base}  compare={compare}",
                "Source: US Bureau of Labor Statistics (CPS, LAUS, CES, JOLTS, OEWS).",
                "AI-exposure: GPTs-are-GPTs (Eloundou et al.), AIOE/AIIE (Felten, Raj, Seamans).",
                "Correlation, not causation: the 2022-23 window also holds the tech-hiring "
                "unwind and Fed rate hikes.",
            ]})
        readme.to_excel(writer, sheet_name="README", index=False)
        for name, df in frames.items():
            (df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)).to_excel(
                writer, sheet_name=name[:31], index=False)
    return out_path
