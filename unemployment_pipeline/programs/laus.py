"""LAUS state + metro series (LA). IDs built from verified templates."""
from __future__ import annotations

from unemployment_pipeline.config import GeoScope, Program, Seasonal, SeriesSpec
from unemployment_pipeline.programs.constants import AI_METROS, LAUS_MEASURES, STATE_FIPS

_LAUS_START = 1976
_METRO_START = 1990


def _statewide_id(seasonal: Seasonal, fips: str, measure: str) -> str:
    s = "S" if seasonal is Seasonal.SA else "U"
    # LA + seasonal + ST + FIPS(2) + 11 zeros + measure(2) = 20 chars
    return f"LA{s}ST{fips}{'0' * 11}{measure}"


def _metro_id(fips: str, cbsa: str, measure: str) -> str:
    # LA + U + MT + FIPS(2) + CBSA(5) + 6 zeros + measure(2) = 20 chars (NSA only)
    return f"LAUMT{fips}{cbsa}{'0' * 6}{measure}"


def laus_specs(geo_scope: GeoScope) -> list[SeriesSpec]:
    """Statewide (SA+NSA) for all states; metros (NSA) when scope includes them."""
    specs: list[SeriesSpec] = []
    for fips, abbr, name in STATE_FIPS:
        for seasonal in (Seasonal.SA, Seasonal.NSA):
            for measure_code, (measure, unit) in LAUS_MEASURES.items():
                specs.append(SeriesSpec(
                    _statewide_id(seasonal, fips, measure_code),
                    Program.LAUS, f"{name}: {measure}", seasonal, _LAUS_START,
                    geo_level="state", geo_code=fips, geo_name=name,
                    measure=measure, unit=unit,
                ))
    if geo_scope in (GeoScope.STATES_METROS, GeoScope.INCLUDE_COUNTIES):
        for cbsa, fips, name in AI_METROS:
            for measure_code, (measure, unit) in LAUS_MEASURES.items():
                specs.append(SeriesSpec(
                    _metro_id(fips, cbsa, measure_code),
                    Program.LAUS, f"{name}: {measure}", Seasonal.NSA, _METRO_START,
                    geo_level="metro", geo_code=cbsa, geo_name=name,
                    measure=measure, unit=unit,
                ))
    return specs
