"""Pure data-prep: turn the long observations frame into chart-ready frames."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from unemployment_pipeline.programs.constants import STATE_FIPS

CHATGPT_LAUNCH = pd.Timestamp("2022-11-30")

_EDU_SERIES = {
    "LNS14027659": "less_than_hs",
    "LNS14027660": "high_school",
    "LNS14027689": "some_college",
    "LNS14027662": "bachelors_plus",
}

_AI_SECTORS = {
    "CES0000000001": "Total nonfarm",
    "CES5000000001": "Information",
    "CES6000000001": "Professional & business services",
}

_FIPS_TO_ABBR = {fips: abbr for fips, abbr, _ in STATE_FIPS}
_FIPS_TO_NAME = {fips: name for fips, _, name in STATE_FIPS}


def load_observations(cache_dir: Path = Path("data/cache")) -> pd.DataFrame:
    return pd.read_parquet(Path(cache_dir) / "observations.parquet")


def _series(obs: pd.DataFrame, series_id: str) -> pd.DataFrame:
    return obs[obs["series_id"] == series_id][["date", "value"]].sort_values("date")


def ur_timeseries(obs: pd.DataFrame, series_id: str = "LNS14000000") -> pd.DataFrame:
    return _series(obs, series_id).reset_index(drop=True)


def education_gradient(obs: pd.DataFrame) -> pd.DataFrame:
    sub = obs[obs["series_id"].isin(_EDU_SERIES)].copy()
    sub["edu"] = sub["series_id"].map(_EDU_SERIES)
    wide = sub.pivot_table(index="date", columns="edu", values="value", aggfunc="last")
    wide = wide.reset_index()
    if {"high_school", "bachelors_plus"} <= set(wide.columns):
        wide["gap_hs_minus_bach"] = wide["high_school"] - wide["bachelors_plus"]
    return wide.sort_values("date").reset_index(drop=True)


def ai_sector_index(obs: pd.DataFrame, base_date: str = "2022-11-30") -> pd.DataFrame:
    base = pd.Timestamp(base_date)
    frames = []
    for sid, label in _AI_SECTORS.items():
        s = _series(obs, sid).dropna()
        if s.empty:
            continue
        at_base = s[s["date"] <= base]
        if at_base.empty:
            continue
        base_val = at_base.iloc[-1]["value"]
        s = s.copy()
        s[label] = s["value"] / base_val * 100.0
        frames.append(s[["date", label]].set_index("date"))
    if not frames:
        return pd.DataFrame(columns=["date"])
    out = pd.concat(frames, axis=1).reset_index()
    return out.sort_values("date").reset_index(drop=True)


def jolts_openings_hires(obs: pd.DataFrame, industry6: str = "000000") -> pd.DataFrame:
    openings = _series(obs, f"JTS{industry6}000000000JOL").rename(columns={"value": "openings"})
    hires = _series(obs, f"JTS{industry6}000000000HIL").rename(columns={"value": "hires"})
    return openings.merge(hires, on="date", how="outer").sort_values("date").reset_index(drop=True)


def tightness_ratio(obs: pd.DataFrame) -> pd.DataFrame:
    unemp = _series(obs, "LNS13000000").rename(columns={"value": "unemployed"})
    openings = _series(obs, "JTS000000000000000JOL").rename(columns={"value": "openings"})
    merged = unemp.merge(openings, on="date", how="inner")
    merged["ratio"] = merged["unemployed"] / merged["openings"]
    return merged[["date", "ratio"]].sort_values("date").reset_index(drop=True)


def state_latest_ur(obs: pd.DataFrame) -> pd.DataFrame:
    mask = obs["series_id"].str.match(r"^LASST\d{2}0+3$") & \
        obs["series_id"].str.startswith("LASST")
    sub = obs[obs["series_id"].str.startswith("LASST") & obs["series_id"].str.endswith("03")].copy()
    if sub.empty:
        return pd.DataFrame(columns=["fips", "abbr", "name", "ur"])
    sub["fips"] = sub["series_id"].str[5:7]
    latest = sub.sort_values("date").groupby("fips", as_index=False).last()
    latest["abbr"] = latest["fips"].map(_FIPS_TO_ABBR)
    latest["name"] = latest["fips"].map(_FIPS_TO_NAME)
    latest = latest.rename(columns={"value": "ur"})
    return latest[["fips", "abbr", "name", "ur"]].dropna(subset=["abbr"]).reset_index(drop=True)


def occupation_exposure(
    obs: pd.DataFrame,
    meta: pd.DataFrame,
    exposure_occ: pd.DataFrame,
) -> pd.DataFrame:
    """OEWS latest employment per occupation joined to GPTs exposure (beta)."""
    oe = obs[obs["series_id"].str.startswith("OEU") & obs["series_id"].str.endswith("01")].copy()
    if oe.empty:
        return pd.DataFrame(columns=["soc6", "label", "employment", "gpts_beta"])
    oe = oe.sort_values("date").groupby("series_id", as_index=False).last()
    m = meta.set_index("series_id")
    oe["soc6"] = oe["series_id"].map(m["occupation_soc"]) if "occupation_soc" in m else None
    oe["label"] = oe["series_id"].map(m["label"]) if "label" in m else oe["series_id"]
    oe = oe.rename(columns={"value": "employment"})
    out = oe.merge(exposure_occ[["soc6", "gpts_beta"]], on="soc6", how="left")
    return out[["soc6", "label", "employment", "gpts_beta"]].dropna(subset=["gpts_beta"]).reset_index(drop=True)


def _value_asof(obs: pd.DataFrame, series_id: str, asof: pd.Timestamp) -> Optional[float]:
    s = obs[(obs["series_id"] == series_id) & (obs["date"] <= asof)].dropna(subset=["value"])
    return float(s.sort_values("date").iloc[-1]["value"]) if not s.empty else None


def _latest(obs: pd.DataFrame, series_id: str) -> tuple[Optional[pd.Timestamp], Optional[float]]:
    s = obs[obs["series_id"] == series_id].dropna(subset=["value"]).sort_values("date")
    if s.empty:
        return None, None
    row = s.iloc[-1]
    return row["date"], float(row["value"])


def _pct(new: Optional[float], old: Optional[float]) -> Optional[float]:
    if new is None or old is None or old == 0:
        return None
    return (new / old - 1.0) * 100.0


_CES_AGGREGATE_CODES = {"00000000", "05000000", "06000000", "07000000", "08000000"}
_JOLTS_AGGREGATE_CODES = {"000000", "100000"}


def _clean_label(raw: object) -> str:
    """Turn a verbose BLS series label into a short industry name."""
    s = str(raw).strip()
    if ":" in s:
        head = s.split(":")[0].strip()
        if head and not head.lower().startswith(("all employees", "jolts")):
            s = head
    s = s.replace("All employees, thousands,", "").replace(", seasonally adjusted", "")
    s = s.strip().strip(",").strip()
    if s.lower().startswith("jolts"):
        if " - " in s:
            s = s.split(" - ", 1)[1]
        s = s.split(" (")[0].strip()
    return s[:1].upper() + s[1:] if s else s


def industry_employment_change(obs: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """Rank CES national industries by employment change since ChatGPT, YoY, 3yr."""
    ind = meta[(meta["program"] == "CES") & (meta.get("geo_level") == "national")
               & (meta["measure"] == "ces_01")]
    if "seasonal" in ind.columns:  # avoid SA/NSA duplicates
        ind = ind[ind["seasonal"] != "NSA"]
    rows = []
    for _, m in ind.iterrows():
        sid = m["series_id"]
        latest_date, latest_val = _latest(obs, sid)
        if latest_date is None:
            continue
        base = _value_asof(obs, sid, CHATGPT_LAUNCH)
        yoy = _value_asof(obs, sid, latest_date - pd.DateOffset(years=1))
        y3 = _value_asof(obs, sid, latest_date - pd.DateOffset(years=3))
        code = sid[3:11] if sid.startswith("CE") else ""
        rows.append({
            "series_id": sid,
            "label": _clean_label(m.get("label")),
            "industry_naics": m.get("industry_naics"),
            "is_aggregate": code in _CES_AGGREGATE_CODES,
            "latest": latest_val,
            "latest_date": latest_date,
            "chg_since_chatgpt_pct": _pct(latest_val, base),
            "chg_yoy_pct": _pct(latest_val, yoy),
            "chg_3y_pct": _pct(latest_val, y3),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = out.drop_duplicates(subset="label", keep="first")
    return out.sort_values("chg_since_chatgpt_pct", ascending=False,
                           na_position="last").reset_index(drop=True)


def education_distribution(obs: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """Employment by educational attainment over time, with within-period shares."""
    emp = meta[(meta["program"] == "CPS") & (meta["measure"] == "employment_level")
               & meta["education"].notna()].copy()
    if emp.empty:
        return pd.DataFrame(columns=["date", "education", "employment", "share"])
    # prefer seasonally adjusted; keep one series per attainment to avoid double counting
    if "seasonal" in emp.columns:
        emp["_pri"] = (emp["seasonal"] != "SA").astype(int)
        emp = emp.sort_values("_pri").drop_duplicates(subset="education", keep="first")
    id_to_edu = dict(zip(emp["series_id"], emp["education"]))
    sub = obs[obs["series_id"].isin(id_to_edu)].copy()
    sub["education"] = sub["series_id"].map(id_to_edu)
    sub = sub.rename(columns={"value": "employment"})
    totals = sub.groupby("date")["employment"].transform("sum")
    sub["share"] = sub["employment"] / totals
    return sub[["date", "education", "employment", "share"]].sort_values(
        ["date", "education"]).reset_index(drop=True)


def jolts_industry_change(obs: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    """Rank JOLTS industries by openings (and hires) change since ChatGPT."""
    op = meta[(meta["program"] == "JOLTS") & (meta["measure"] == "jolts_job_openings_level")]
    hi = meta[(meta["program"] == "JOLTS") & (meta["measure"] == "jolts_hires_level")]
    hi_by_label = dict(zip(hi["label"], hi["series_id"]))
    rows = []
    for _, m in op.iterrows():
        sid = m["series_id"]
        latest_date, latest_val = _latest(obs, sid)
        if latest_date is None:
            continue
        base = _value_asof(obs, sid, CHATGPT_LAUNCH)
        label = m.get("label")
        hi_sid = hi_by_label.get(label)
        hi_latest = _latest(obs, hi_sid)[1] if hi_sid else None
        hi_base = _value_asof(obs, hi_sid, CHATGPT_LAUNCH) if hi_sid else None
        code = sid[3:9] if sid.startswith("JT") else ""
        rows.append({
            "series_id": sid,
            "label": _clean_label(label),
            "is_aggregate": code in _JOLTS_AGGREGATE_CODES,
            "openings_latest": latest_val,
            "openings_chg_since_chatgpt_pct": _pct(latest_val, base),
            "hires_chg_since_chatgpt_pct": _pct(hi_latest, hi_base),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = out.drop_duplicates(subset="label", keep="first")
    return out.sort_values("openings_chg_since_chatgpt_pct", ascending=True,
                           na_position="last").reset_index(drop=True)


def national_kpis(obs: pd.DataFrame) -> dict[str, Optional[float]]:
    def latest(sid: str) -> Optional[float]:
        s = _series(obs, sid).dropna()
        return float(s.iloc[-1]["value"]) if not s.empty else None

    return {
        "unemployment_rate": latest("LNS14000000"),
        "lfpr": latest("LNS11300000"),
        "emp_pop": latest("LNS12300000"),
        "openings": latest("JTS000000000000000JOL"),
        "hires": latest("JTS000000000000000HIL"),
        "quits_rate": latest("JTS000000000000000QUR"),
        "ur_bachelors": latest("LNS14027662"),
        "ur_less_hs": latest("LNS14027659"),
    }
