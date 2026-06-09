"""CES national (CE) + State/Metro (SM) employment series."""
from __future__ import annotations

from unemployment_pipeline.config import Program, Seasonal, SeriesSpec
from unemployment_pipeline.programs.constants import (
    AI_METROS,
    CES_SUPERSECTORS,
    STATE_FIPS,
)

# National data types to pull: 01 all employees, 02 weekly hours, 03 hourly earnings.
_CE_DATATYPES: list[tuple[str, str, str]] = [
    ("01", "all employees (000s)", "persons_thousands"),
    ("02", "avg weekly hours", "hours"),
    ("03", "avg hourly earnings", "dollars"),
]


def _ce_id(seasonal: Seasonal, industry8: str, datatype: str) -> str:
    s = "S" if seasonal is Seasonal.SA else "U"
    return f"CE{s}{industry8}{datatype}"  # 13 chars


def _sm_id(seasonal: Seasonal, fips: str, area5: str, industry8: str, datatype: str) -> str:
    s = "S" if seasonal is Seasonal.SA else "U"
    return f"SM{s}{fips}{area5}{industry8}{datatype}"  # 20 chars


def ces_specs() -> list[SeriesSpec]:
    specs: list[SeriesSpec] = []
    # National supersectors
    for industry8, label, naics, ai in CES_SUPERSECTORS:
        start = 1939 if industry8 == "00000000" else 1990
        # all-employees in SA and NSA; hours/earnings only for total private as leading indicator
        for datatype, dt_label, unit in _CE_DATATYPES:
            if datatype != "01" and industry8 != "05000000":
                continue
            for seasonal in (Seasonal.SA, Seasonal.NSA) if datatype == "01" else (Seasonal.SA,):
                specs.append(SeriesSpec(
                    _ce_id(seasonal, industry8, datatype),
                    Program.CES, f"{label}: {dt_label}", seasonal, start,
                    geo_level="national", industry_naics=naics or None,
                    measure=f"ces_{datatype}", unit=unit,
                ))
    # State & metro: total nonfarm + AI sectors (Information, PBS), all employees SA
    ai_industries = [(i, lbl, naics) for (i, lbl, naics, ai) in CES_SUPERSECTORS
                     if i in ("00000000", "50000000", "60000000")]
    for fips, abbr, name in STATE_FIPS:
        for industry8, label, naics in ai_industries:
            specs.append(SeriesSpec(
                _sm_id(Seasonal.SA, fips, "00000", industry8, "01"),
                Program.CES, f"{name}: {label} all employees", Seasonal.SA, 1990,
                geo_level="state", geo_code=fips, geo_name=name,
                industry_naics=naics or None, measure="ces_01", unit="persons_thousands",
            ))
    for cbsa, fips, name in AI_METROS:
        for industry8, label, naics in ai_industries:
            specs.append(SeriesSpec(
                _sm_id(Seasonal.SA, fips, cbsa, industry8, "01"),
                Program.CES, f"{name}: {label} all employees", Seasonal.SA, 1990,
                geo_level="metro", geo_code=cbsa, geo_name=name,
                industry_naics=naics or None, measure="ces_01", unit="persons_thousands",
            ))
    return specs
