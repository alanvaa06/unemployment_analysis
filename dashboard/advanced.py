"""Pure prepare functions for the advanced visualization suite.

Decompositions, distributions, dispersion, diffusion, event-study, and
exposure relationships. No IO; all functions take the tidy obs/meta frames.
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd

from dashboard.prepare import _value_asof, _latest  # reuse helpers
from unemployment_pipeline.programs.constants import STATE_FIPS

CHATGPT = pd.Timestamp("2022-11-30")
_FIPS_TO_ABBR = {fips: abbr for fips, abbr, _ in STATE_FIPS}

# Clean, non-overlapping CES leaf set that sums to ~total nonfarm (for waterfall + diffusion).
LEAF_PARTITION: list[tuple[str, str, str]] = [
    ("CES1000000001", "Mining & logging", "21"),
    ("CES2000000001", "Construction", "23"),
    ("CES3100000001", "Durable goods mfg", "31-33"),
    ("CES3200000001", "Nondurable goods mfg", "31-33"),
    ("CES4142000001", "Wholesale trade", "42"),
    ("CES4200000001", "Retail trade", "44-45"),
    ("CES4300000001", "Transportation & warehousing", "48-49"),
    ("CES4422000001", "Utilities", "22"),
    ("CES5000000001", "Information", "51"),
    ("CES5500000001", "Financial activities", "52-53"),
    ("CES6000000001", "Professional & business svcs", "54-56"),
    ("CES6500000001", "Education & health svcs", "61-62"),
    ("CES7000000001", "Leisure & hospitality", "71-72"),
    ("CES8000000001", "Other services", "81"),
    ("CES9000000001", "Government", "90"),
]

# Spotlight set for distribution/scatter/heatmap (no parent shown with its child).
DISPLAY_INDUSTRIES: list[tuple[str, str, str]] = [
    ("CES1000000001", "Mining & logging", "21"),
    ("CES2000000001", "Construction", "23"),
    ("CES3100000001", "Durable goods mfg", "31-33"),
    ("CES3200000001", "Nondurable goods mfg", "31-33"),
    ("CES4142000001", "Wholesale trade", "42"),
    ("CES4200000001", "Retail trade", "44-45"),
    ("CES4300000001", "Transportation & warehousing", "48-49"),
    ("CES4422000001", "Utilities", "22"),
    ("CES5500000001", "Financial activities", "52-53"),
    ("CES6500000001", "Education & health svcs", "61-62"),
    ("CES7000000001", "Leisure & hospitality", "71-72"),
    ("CES8000000001", "Other services", "81"),
    ("CES9000000001", "Government", "90"),
    # AI-relevant detail (Information sub-industries + computer systems design)
    ("CES5051320001", "Software publishers", "5132"),
    ("CES5051800001", "Data processing & hosting", "518"),
    ("CES6054150001", "Computer systems design", "5415"),
    ("CES5051700001", "Telecommunications", "517"),
    ("CES5051200001", "Motion picture & sound", "512"),
    ("CES5051600001", "Broadcasting & content", "516"),
    ("CES5051900001", "Web search & other info", "519"),
]

_AI_NAICS = {"5132", "518", "5415", "517", "512", "516", "519", "51", "54-56"}

# Map each CES industry to the AIIE 4-digit NAICS codes (or 2-digit prefixes) it spans,
# so a sector-level AIIE = mean of AIIE over matching 4-digit codes.
_AIIE_KEYS: dict[str, list[str]] = {
    "CES1000000001": ["21"], "CES2000000001": ["23"],
    "CES3100000001": ["31", "32", "33"], "CES3200000001": ["31", "32", "33"],
    "CES4142000001": ["42"], "CES4200000001": ["44", "45"],
    "CES4300000001": ["48", "49"], "CES4422000001": ["22"],
    "CES5000000001": ["51"], "CES5500000001": ["52", "53"],
    "CES6000000001": ["54", "55", "56"], "CES6500000001": ["61", "62"],
    "CES7000000001": ["71", "72"], "CES8000000001": ["81"], "CES9000000001": [],
    "CES5051320001": ["5112"], "CES5051800001": ["5182"], "CES6054150001": ["5415"],
    "CES5051700001": [], "CES5051200001": ["5121"], "CES5051600001": ["5151", "5152"],
    "CES5051900001": ["5191"],
}


def _aiie_for(exposure_ind: pd.DataFrame, sid: str) -> float:
    keys = _AIIE_KEYS.get(sid, [])
    if not keys or exposure_ind.empty:
        return float("nan")
    naics = exposure_ind["naics"].astype(str)
    mask = pd.Series(False, index=exposure_ind.index)
    for k in keys:
        mask = mask | (naics == k if len(k) == 4 else naics.str.startswith(k))
    vals = exposure_ind.loc[mask, "aiie"]
    return float(vals.mean()) if len(vals) else float("nan")


def _present(obs: pd.DataFrame, ids: Sequence[str]) -> list[str]:
    have = set(obs["series_id"].unique())
    return [i for i in ids if i in have]


def _pct(new: Optional[float], old: Optional[float]) -> Optional[float]:
    if new is None or old is None or old == 0:
        return None
    return (new / old - 1.0) * 100.0


def contribution_waterfall(obs: pd.DataFrame, meta: pd.DataFrame,
                           baseline: str, compare: str) -> pd.DataFrame:
    """Per-industry contribution (thousands of jobs) to net change, baseline->compare."""
    b = pd.Timestamp(baseline + "-01") + pd.offsets.MonthEnd(0)
    c = pd.Timestamp(compare + "-01") + pd.offsets.MonthEnd(0)
    rows = []
    for sid, label, naics in LEAF_PARTITION:
        emp_b = _value_asof(obs, sid, b)
        emp_c = _value_asof(obs, sid, c)
        if emp_b is None or emp_c is None:
            continue
        rows.append({"series_id": sid, "label": label, "naics": naics,
                     "contribution_k": emp_c - emp_b})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values("contribution_k", ascending=False).reset_index(drop=True)


def industry_change_distribution(obs: pd.DataFrame, meta: pd.DataFrame,
                                 exposure_ind: pd.DataFrame,
                                 baseline: str, compare: str) -> pd.DataFrame:
    """% change per DISPLAY industry baseline->compare, with AIIE + employment."""
    b = pd.Timestamp(baseline + "-01") + pd.offsets.MonthEnd(0)
    c = pd.Timestamp(compare + "-01") + pd.offsets.MonthEnd(0)
    rows = []
    for sid, label, naics in DISPLAY_INDUSTRIES:
        emp_b = _value_asof(obs, sid, b)
        emp_c = _value_asof(obs, sid, c)
        if emp_b is None or emp_c is None:
            continue
        rows.append({"series_id": sid, "label": label, "naics": naics,
                     "pct_change": _pct(emp_c, emp_b), "employment": emp_c,
                     "aiie": _aiie_for(exposure_ind, sid), "ai_flag": naics in _AI_NAICS})
    return pd.DataFrame(rows).dropna(subset=["pct_change"]).reset_index(drop=True)


def diffusion_index(obs: pd.DataFrame, window_months: int = 1) -> pd.DataFrame:
    """Share (0-100) of LEAF_PARTITION industries growing over a trailing window."""
    ids = _present(obs, [s for s, _, _ in LEAF_PARTITION])
    if not ids:
        return pd.DataFrame(columns=["date", "diffusion"])
    wide = (obs[obs["series_id"].isin(ids)]
            .pivot_table(index="date", columns="series_id", values="value")
            .sort_index())
    chg = wide - wide.shift(window_months)
    grew = (chg > 0).sum(axis=1)
    valid = chg.notna().sum(axis=1)
    diffusion = (grew / valid.replace(0, np.nan)) * 100.0
    out = diffusion.dropna().reset_index()
    out.columns = ["date", "diffusion"]
    return out


def state_ur_dispersion(obs: pd.DataFrame) -> pd.DataFrame:
    """Per-month cross-state UR percentiles + labor-force-weighted std dev."""
    ur = obs[obs["series_id"].str.startswith("LASST") & obs["series_id"].str.endswith("03")].copy()
    lf = obs[obs["series_id"].str.startswith("LASST") & obs["series_id"].str.endswith("06")].copy()
    if ur.empty:
        return pd.DataFrame(columns=["date", "p10", "p25", "p50", "p75", "p90", "wstd"])
    ur["fips"] = ur["series_id"].str[5:7]
    lf["fips"] = lf["series_id"].str[5:7]
    lfw = lf[["date", "fips", "value"]].rename(columns={"value": "lf"})
    m = ur[["date", "fips", "value"]].rename(columns={"value": "ur"}).merge(
        lfw, on=["date", "fips"], how="left")
    out = []
    for date, g in m.groupby("date"):
        urs = g["ur"].dropna()
        if urs.empty:
            continue
        w = g["lf"].fillna(g["lf"].mean() if g["lf"].notna().any() else 1.0)
        w = w.where(w > 0, 1.0)
        mean = np.average(g["ur"], weights=w)
        wstd = float(np.sqrt(np.average((g["ur"] - mean) ** 2, weights=w)))
        out.append({"date": date, "p10": urs.quantile(.10), "p25": urs.quantile(.25),
                    "p50": urs.quantile(.50), "p75": urs.quantile(.75),
                    "p90": urs.quantile(.90), "wstd": wstd})
    return pd.DataFrame(out).sort_values("date").reset_index(drop=True)


def beveridge_series(obs: pd.DataFrame,
                     ur_id: str = "LNS14000000",
                     openings_rate_id: str = "JTS000000000000000JOR") -> pd.DataFrame:
    """Monthly (unemployment rate, job-openings rate) for the Beveridge curve."""
    u = obs[obs["series_id"] == ur_id][["date", "value"]].rename(columns={"value": "u"})
    v = obs[obs["series_id"] == openings_rate_id][["date", "value"]].rename(columns={"value": "v"})
    m = u.merge(v, on="date", how="inner").dropna().sort_values("date")
    m["year"] = m["date"].dt.year
    return m.reset_index(drop=True)


def event_study_indexed(obs: pd.DataFrame, anchor: str, treated_id: str,
                        control_ids: Sequence[str]) -> pd.DataFrame:
    """Treated and (mean) control employment indexed to 100 at the anchor month."""
    a = pd.Timestamp(anchor + "-01") + pd.offsets.MonthEnd(0)

    def indexed(series_id: str) -> Optional[pd.Series]:
        s = obs[obs["series_id"] == series_id].set_index("date")["value"].sort_index()
        base = _value_asof(obs, series_id, a)
        if s.empty or base in (None, 0):
            return None
        return s / base * 100.0

    treated = indexed(treated_id)
    if treated is None:
        return pd.DataFrame(columns=["date", "treated", "control"])
    controls = [indexed(c) for c in control_ids]
    controls = [c for c in controls if c is not None]
    df = pd.DataFrame({"treated": treated})
    if controls:
        df["control"] = pd.concat(controls, axis=1).mean(axis=1)
    return df.reset_index().rename(columns={"index": "date"}).sort_values("date").reset_index(drop=True)


def freeze_vs_cuts(obs: pd.DataFrame, meta: pd.DataFrame,
                   baseline: str, compare: str) -> pd.DataFrame:
    """Per JOLTS INDUSTRY: openings change vs layoffs change, baseline->compare.

    Joins openings and layoffs on the JOLTS industry code (positions 3:9), national
    only, excluding total-nonfarm/total-private aggregates. Keeps industries with both.
    """
    from dashboard.prepare import _clean_label
    b = pd.Timestamp(baseline + "-01") + pd.offsets.MonthEnd(0)
    c = pd.Timestamp(compare + "-01") + pd.offsets.MonthEnd(0)
    jt = meta[(meta["program"] == "JOLTS") & (meta.get("geo_level") != "region")]

    def code(sid: str) -> str:
        return sid[3:9] if isinstance(sid, str) and sid.startswith("JT") else ""

    op = {code(r.series_id): r for r in jt[jt["measure"] == "jolts_job_openings_level"].itertuples()}
    ld = {code(r.series_id): r.series_id
          for r in jt[jt["measure"] == "jolts_layoffs_discharges_level"].itertuples()}
    rows = []
    for ind_code, m in op.items():
        if ind_code in ("000000", "100000") or ind_code not in ld:
            continue
        ob, oc = _value_asof(obs, m.series_id, b), _value_asof(obs, m.series_id, c)
        lb, lc = _value_asof(obs, ld[ind_code], b), _value_asof(obs, ld[ind_code], c)
        if None in (ob, oc, lb, lc):
            continue
        rows.append({"label": _clean_label(m.label), "openings_chg": _pct(oc, ob),
                     "layoffs_chg": _pct(lc, lb), "employment": oc})
    return pd.DataFrame(rows).dropna(subset=["openings_chg", "layoffs_chg"]).reset_index(drop=True)


def exposure_industry_change(obs: pd.DataFrame, meta: pd.DataFrame,
                             exposure_ind: pd.DataFrame,
                             baseline: str, compare: str) -> pd.DataFrame:
    """Join AIIE to industry % employment change (DISPLAY set), drop unmatched."""
    dist = industry_change_distribution(obs, meta, exposure_ind, baseline, compare)
    return dist.dropna(subset=["aiie"]).reset_index(drop=True)


def _sm_id(fips: str, industry8: str) -> str:
    return f"SMS{fips}00000{industry8}01"


def state_ur_change_techshare(obs: pd.DataFrame, baseline: str, compare: str) -> pd.DataFrame:
    """Per state: change in unemployment rate (pp) and tech-employment share (%)."""
    b = pd.Timestamp(baseline + "-01") + pd.offsets.MonthEnd(0)
    c = pd.Timestamp(compare + "-01") + pd.offsets.MonthEnd(0)
    ur = obs[obs["series_id"].str.startswith("LASST") & obs["series_id"].str.endswith("03")]
    fips_list = sorted({s[5:7] for s in ur["series_id"].unique()})
    rows = []
    for fips in fips_list:
        ur_id = f"LASST{fips}0000000000003"
        ub, uc = _value_asof(obs, ur_id, b), _value_asof(obs, ur_id, c)
        if ub is None or uc is None:
            continue
        tot = _latest(obs, _sm_id(fips, "00000000"))[1]
        info = _latest(obs, _sm_id(fips, "50000000"))[1]
        pbs = _latest(obs, _sm_id(fips, "60000000"))[1]
        tech = ((info or 0) + (pbs or 0)) / tot * 100 if tot else float("nan")
        rows.append({"fips": fips, "abbr": _FIPS_TO_ABBR.get(fips),
                     "name": None, "d_ur": uc - ub, "tech_share": tech})
    out = pd.DataFrame(rows).dropna(subset=["abbr"]).reset_index(drop=True)
    return out


def change_distribution(obs: pd.DataFrame, exposed_ids: Sequence[str],
                        other_ids: Sequence[str], since: str = "2023-01",
                        window: int = 12) -> pd.DataFrame:
    """Pooled distribution of `window`-month % employment changes since `since`,
    tagged AI-exposed vs Other (for an honest large-N histogram)."""
    cutoff = pd.Timestamp(since + "-01")
    groups = {"AI-exposed": list(exposed_ids), "Other": list(other_ids)}
    rows = []
    for group, ids in groups.items():
        for sid in ids:
            s = (obs[obs["series_id"] == sid].dropna(subset=["value"])
                 .sort_values("date").set_index("date")["value"])
            if s.empty:
                continue
            pct = (s / s.shift(window) - 1.0) * 100.0
            pct = pct[pct.index >= cutoff].dropna()
            for v in pct:
                rows.append({"group": group, "pct": float(v)})
    return pd.DataFrame(rows)


def advanced_bundle(obs: pd.DataFrame, meta: pd.DataFrame,
                    exposure_ind: pd.DataFrame) -> dict:
    """Compact JSON-ready bundle for client-side recompute of the interactive charts."""
    from dashboard.bundle import _monthly, monthly_sector_bundle
    from dashboard.prepare import _clean_label

    seen, industries = set(), []
    for sid, label, naics in LEAF_PARTITION + DISPLAY_INDUSTRIES:
        if sid in seen:
            continue
        dates, values = _monthly(obs, sid)
        if not dates:
            continue
        seen.add(sid)
        aiie = _aiie_for(exposure_ind, sid)
        industries.append({
            "key": sid, "label": label, "naics": naics,
            "aiie": None if (aiie != aiie) else round(aiie, 3),  # NaN -> None
            "leaf": sid in {s for s, _, _ in LEAF_PARTITION},
            "display": sid in {s for s, _, _ in DISPLAY_INDUSTRIES},
            "ai": naics in _AI_NAICS,
            "dates": dates, "values": values,
        })

    jt = meta[(meta["program"] == "JOLTS") & (meta.get("geo_level") != "region")]
    jolts = []
    for measure, element in (("jolts_job_openings_level", "openings"),
                             ("jolts_layoffs_discharges_level", "layoffs")):
        for r in jt[jt["measure"] == measure].itertuples():
            code = r.series_id[3:9]
            if code in ("000000", "100000"):
                continue
            dates, values = _monthly(obs, r.series_id)
            if not dates:
                continue
            jolts.append({"code": code, "label": _clean_label(r.label),
                          "element": element, "dates": dates, "values": values})
    # states: monthly UR + a tech-employment-share scalar (for the beeswarm)
    states = []
    ur = obs[obs["series_id"].str.startswith("LASST") & obs["series_id"].str.endswith("03")]
    for fips in sorted({s[5:7] for s in ur["series_id"].unique()}):
        dates, values = _monthly(obs, f"LASST{fips}0000000000003")
        if not dates:
            continue
        tot = _latest(obs, _sm_id(fips, "00000000"))[1]
        info = _latest(obs, _sm_id(fips, "50000000"))[1]
        pbs = _latest(obs, _sm_id(fips, "60000000"))[1]
        tech = round(((info or 0) + (pbs or 0)) / tot * 100, 2) if tot else None
        states.append({"abbr": _FIPS_TO_ABBR.get(fips), "tech": tech,
                       "dates": dates, "values": values})
    # detailed industries (4-digit NAICS) for the dense beeswarm, colored by AIIE
    aiie_map = (dict(zip(exposure_ind["naics"].astype(str), exposure_ind["aiie"]))
                if not exposure_ind.empty else {})
    ces = meta[(meta["program"] == "CES") & (meta.get("geo_level") == "national")
               & (meta["measure"] == "ces_01")]
    detailed = []
    for r in ces.itertuples():
        naics = str(getattr(r, "industry_naics", "") or "")
        if len(naics) != 4:
            continue
        dates, values = _monthly(obs, r.series_id)
        if not dates:
            continue
        a = aiie_map.get(naics)
        detailed.append({"key": r.series_id, "label": r.label, "naics": naics,
                         "aiie": None if a is None or a != a else round(float(a), 3),
                         "dates": dates, "values": values})
    return {"industries": industries, "jolts": jolts, "sectors": monthly_sector_bundle(obs),
            "states": states, "detailed": detailed}


def ols_slope(x: Sequence[float], y: Sequence[float]) -> tuple[float, float, float]:
    """Return (slope, intercept, r_squared) for a simple least-squares fit."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if len(x) < 2 or x.std() == 0:
        return 0.0, float(y.mean()) if len(y) else 0.0, 0.0
    slope, intercept = np.polyfit(x, y, 1)
    yhat = slope * x + intercept
    ss_res = float(((y - yhat) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return float(slope), float(intercept), r2
