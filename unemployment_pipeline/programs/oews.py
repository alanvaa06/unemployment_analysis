"""OEWS occupational employment & wages (OE). National AI-exposed occupations.

OEWS is an annual, not-seasonally-adjusted snapshot (annual_only=True).
"""
from __future__ import annotations

from unemployment_pipeline.config import Program, Seasonal, SeriesSpec
from unemployment_pipeline.programs.constants import AI_SOC

_OEWS_START = 2014  # 2018-SOC consistent era; client fetches whatever annual obs exist.

# data type: 01 employment, 04 mean annual wage, 13 median annual wage.
_OE_DATATYPES: list[tuple[str, str, str]] = [
    ("01", "employment", "persons"),
    ("04", "mean annual wage", "dollars"),
    ("13", "median annual wage", "dollars"),
]


def _oe_id(soc6: str, datatype: str) -> str:
    # OE + U + areatype N + area(7) + industry(6) + occupation(6) + datatype(2) = 25 chars
    return f"OEUN{'0' * 7}{'000000'}{soc6}{datatype}"


def oews_specs() -> list[SeriesSpec]:
    specs: list[SeriesSpec] = []
    for soc6, label, ai in AI_SOC:
        for datatype, dt_label, unit in _OE_DATATYPES:
            specs.append(SeriesSpec(
                _oe_id(soc6, datatype),
                Program.OEWS, f"{label}: {dt_label}", Seasonal.NSA, _OEWS_START,
                geo_level="national", occupation_soc=soc6,
                measure=f"oews_{datatype}", unit=unit, annual_only=True,
            ))
    return specs
