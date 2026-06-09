"""Build compact, embeddable data bundles for client-side interactivity.

The interactive page embeds these as JSON and recomputes "% change since a
chosen baseline" in the browser. Matrices feed heatmaps and boxplots.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from dashboard.prepare import _CES_AGGREGATE_CODES, _JOLTS_AGGREGATE_CODES, _clean_label
from unemployment_pipeline.programs.constants import STATE_FIPS

_FIPS_TO_ABBR = {fips: abbr for fips, abbr, _ in STATE_FIPS}
_FIPS_TO_NAME = {fips: name for fips, _, name in STATE_FIPS}
_MIN_YEAR = 2007  # trim history for a light payload while covering several baselines


def change_since(dates: list[str], values: list[float],
                 baseline: str, compare: str) -> Optional[float]:
    """Percent change from the last value on/before ``baseline`` to on/before ``compare``.

    Reference implementation; the embedded JavaScript mirrors this exactly.
    """
    def last_on_or_before(target: str) -> Optional[float]:
        chosen = None
        for d, v in zip(dates, values):
            if d <= target and v is not None and not (isinstance(v, float) and np.isnan(v)):
                chosen = v
        return chosen

    base = last_on_or_before(baseline)
    comp = last_on_or_before(compare)
    if base in (None, 0) or comp is None:
        return None
    return (comp / base - 1.0) * 100.0


def _monthly(obs: pd.DataFrame, series_id: str) -> tuple[list[str], list[float]]:
    s = obs[(obs["series_id"] == series_id) & (obs["date"].dt.year >= _MIN_YEAR)]
    s = s.dropna(subset=["value"]).sort_values("date")
    dates = [d.strftime("%Y-%m") for d in s["date"]]
    values = [float(v) for v in s["value"]]
    return dates, values


def monthly_industry_bundle(obs: pd.DataFrame, meta: pd.DataFrame) -> list[dict]:
    """Monthly employment per CES national industry (SA, non-aggregate)."""
    ind = meta[(meta["program"] == "CES") & (meta.get("geo_level") == "national")
               & (meta["measure"] == "ces_01")]
    if "seasonal" in ind.columns:
        ind = ind[ind["seasonal"] != "NSA"]
    out = []
    seen_labels = set()
    for _, m in ind.iterrows():
        sid = m["series_id"]
        code = sid[3:11] if sid.startswith("CE") else ""
        if code in _CES_AGGREGATE_CODES:
            continue
        label = _clean_label(m.get("label"))
        if label in seen_labels:
            continue
        dates, values = _monthly(obs, sid)
        if not dates:
            continue
        seen_labels.add(label)
        out.append({"key": sid, "label": label, "group": "industry",
                    "naics": m.get("industry_naics") or "", "dates": dates, "values": values})
    return out


def monthly_jolts_bundle(obs: pd.DataFrame, meta: pd.DataFrame) -> list[dict]:
    """Monthly JOLTS openings and hires per industry (SA, non-aggregate)."""
    jt = meta[(meta["program"] == "JOLTS")
              & (meta["measure"].isin(["jolts_job_openings_level", "jolts_hires_level"]))]
    out = []
    for _, m in jt.iterrows():
        sid = m["series_id"]
        code = sid[3:9] if sid.startswith("JT") else ""
        if code in _JOLTS_AGGREGATE_CODES:
            continue
        element = "openings" if m["measure"] == "jolts_job_openings_level" else "hires"
        dates, values = _monthly(obs, sid)
        if not dates:
            continue
        out.append({"key": sid, "label": _clean_label(m.get("label")), "element": element,
                    "group": "jolts", "dates": dates, "values": values})
    return out


def monthly_sector_bundle(obs: pd.DataFrame) -> list[dict]:
    """Total nonfarm vs Information vs PBS, monthly (for the rebased index)."""
    sectors = {"CES0000000001": "Total nonfarm", "CES5000000001": "Information",
               "CES6000000001": "Professional & business services"}
    out = []
    for sid, label in sectors.items():
        dates, values = _monthly(obs, sid)
        if dates:
            out.append({"key": sid, "label": label, "group": "sector",
                        "dates": dates, "values": values})
    return out


def state_ur_by_year(obs: pd.DataFrame) -> pd.DataFrame:
    """Annual-average statewide unemployment rate (SA) per state per year."""
    sub = obs[obs["series_id"].str.startswith("LASST") & obs["series_id"].str.endswith("03")].copy()
    if sub.empty:
        return pd.DataFrame(columns=["year", "fips", "abbr", "name", "ur"])
    sub["fips"] = sub["series_id"].str[5:7]
    sub["year"] = sub["date"].dt.year
    g = sub.groupby(["fips", "year"], as_index=False)["value"].mean().rename(columns={"value": "ur"})
    g["abbr"] = g["fips"].map(_FIPS_TO_ABBR)
    g["name"] = g["fips"].map(_FIPS_TO_NAME)
    return g.dropna(subset=["abbr"])[["year", "fips", "abbr", "name", "ur"]].reset_index(drop=True)


def industry_year_matrix(obs: pd.DataFrame, meta: pd.DataFrame,
                         start_year: int = 2016, only_ids=None) -> dict:
    """Heatmap matrix: industries x year, value = YoY % change in annual-avg employment.

    ``only_ids`` restricts to a curated set of series (keeps the heatmap readable;
    the full detailed-industry universe lives in the beeswarm)."""
    bundle = monthly_industry_bundle(obs, meta)
    if only_ids is not None:
        keep = set(only_ids)
        bundle = [b for b in bundle if b["key"] in keep]
    by_label: dict[str, pd.Series] = {}
    for b in bundle:
        df = pd.DataFrame({"date": pd.to_datetime(b["dates"], format="%Y-%m"), "v": b["values"]})
        df["year"] = df["date"].dt.year
        annual = df.groupby("year")["v"].mean()
        by_label[b["label"]] = annual
    years = list(range(start_year, max((s.index.max() for s in by_label.values()), default=start_year) + 1))
    labels, z = [], []
    for label, annual in by_label.items():
        row = []
        for y in years:
            if y in annual.index and (y - 1) in annual.index and annual[y - 1]:
                row.append(round((annual[y] / annual[y - 1] - 1.0) * 100.0, 2))
            else:
                row.append(None)
        labels.append(label)
        z.append(row)
    # order rows by cumulative change (most negative at bottom)
    order = sorted(range(len(labels)),
                   key=lambda i: np.nansum([v for v in z[i] if v is not None]))
    return {"industries": [labels[i] for i in order],
            "years": years, "z": [z[i] for i in order]}
