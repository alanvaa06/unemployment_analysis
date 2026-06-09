"""JOLTS job openings & labor turnover series (JT)."""
from __future__ import annotations

from unemployment_pipeline.config import Program, Seasonal, SeriesSpec
from unemployment_pipeline.programs.constants import (
    JOLTS_ELEMENTS,
    JOLTS_INDUSTRIES,
    JOLTS_REGIONS,
)

_JOLTS_START = 2000


def _jt_id(seasonal: Seasonal, industry6: str, region2: str, element: str, ratelevel: str) -> str:
    s = "S" if seasonal is Seasonal.SA else "U"
    # JT + seas + industry(6) + region(2) + area(5) + size(2) + element(2) + R/L = 21 chars
    return f"JT{s}{industry6}{region2}{'00000'}{'00'}{element}{ratelevel}"


def jolts_specs() -> list[SeriesSpec]:
    specs: list[SeriesSpec] = []
    # National, all industries: every element as level (L); openings/hires/quits also as rate (R).
    for industry6, ind_label, naics, ai in JOLTS_INDUSTRIES:
        for element, elem_label in JOLTS_ELEMENTS.items():
            specs.append(SeriesSpec(
                _jt_id(Seasonal.SA, industry6, "00", element, "L"),
                Program.JOLTS, f"{ind_label}: {elem_label} (level)", Seasonal.SA,
                _JOLTS_START, geo_level="national", industry_naics=naics or None,
                measure=f"jolts_{elem_label}_level", unit="persons_thousands",
            ))
            if element in ("JO", "HI", "QU", "LD"):
                specs.append(SeriesSpec(
                    _jt_id(Seasonal.SA, industry6, "00", element, "R"),
                    Program.JOLTS, f"{ind_label}: {elem_label} (rate)", Seasonal.SA,
                    _JOLTS_START, geo_level="national", industry_naics=naics or None,
                    measure=f"jolts_{elem_label}_rate", unit="percent",
                ))
    # Census regions: total nonfarm openings & hires (level), SA.
    for region2, region_name in JOLTS_REGIONS.items():
        for element in ("JO", "HI"):
            specs.append(SeriesSpec(
                _jt_id(Seasonal.SA, "000000", region2, element, "L"),
                Program.JOLTS, f"{region_name}: {JOLTS_ELEMENTS[element]} (level)",
                Seasonal.SA, _JOLTS_START, geo_level="region", geo_code=region2,
                geo_name=region_name, measure=f"jolts_{JOLTS_ELEMENTS[element]}_level",
                unit="persons_thousands",
            ))
    return specs
