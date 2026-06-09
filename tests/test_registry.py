"""Tests for program enumerators and the registry assembler."""
from __future__ import annotations

import re

from unemployment_pipeline.config import FetchConfig, GeoScope, Program, Seasonal
from unemployment_pipeline.programs.cps import cps_specs
from unemployment_pipeline.programs.ces import ces_specs
from unemployment_pipeline.programs.jolts import jolts_specs
from unemployment_pipeline.programs.laus import laus_specs
from unemployment_pipeline.programs.oews import oews_specs
from unemployment_pipeline.registry import build_registry


def _ids(specs) -> set[str]:
    return {s.series_id for s in specs}


def test_cps_includes_headline_and_education() -> None:
    ids = _ids(cps_specs())
    assert "LNS14000000" in ids  # unemployment rate
    # education quartet (the critical AI cut)
    for sid in ("LNS14027659", "LNS14027660", "LNS14027689", "LNS14027662"):
        assert sid in ids
    assert all(s.program is Program.CPS for s in cps_specs())


def test_laus_state_construction_and_counts() -> None:
    specs = laus_specs(GeoScope.STATES)
    ids = _ids(specs)
    # exact verified California statewide IDs
    assert "LASST060000000000003" in ids  # CA, SA, unemployment rate
    assert "LAUST060000000000003" in ids  # CA, NSA, unemployment rate
    # 52 areas (50 states + DC + PR) x 2 seasonal x 4 measures
    assert len(specs) == 52 * 2 * 4
    pat = re.compile(r"^LA[SU]ST\d{13}0[3-6]$")
    assert all(pat.match(s.series_id) for s in specs)
    assert all(len(s.series_id) == 20 for s in specs)


def test_laus_metros_present_with_states_metros_scope() -> None:
    specs = laus_specs(GeoScope.STATES_METROS)
    ids = _ids(specs)
    assert "LAUMT063108000000003" in ids  # LA metro, NSA, UR
    assert "LAUMT363562000000003" in ids  # NY metro, NSA, UR
    metros = [s for s in specs if s.geo_level == "metro"]
    assert metros and all(len(s.series_id) == 20 for s in metros)
    assert all(s.seasonal is Seasonal.NSA for s in metros)


def test_ces_includes_ai_sectors() -> None:
    ids = _ids(ces_specs())
    assert "CES0000000001" in ids  # total nonfarm
    assert "CES5000000001" in ids  # Information
    assert "CES6000000001" in ids  # Professional & business services
    # state Information series, verified format
    assert "SMS06000005000000001" in ids  # CA statewide Information SA


def test_jolts_elements_and_ai_industries() -> None:
    ids = _ids(jolts_specs())
    assert "JTS000000000000000JOL" in ids  # total nonfarm openings level
    assert "JTS000000000000000HIL" in ids  # total nonfarm hires level
    assert "JTS510000000000000JOL" in ids  # Information openings
    assert "JTS540099000000000HIL" in ids  # PBS hires
    assert all(len(s.series_id) == 21 for s in jolts_specs())


def test_oews_national_ai_occupations() -> None:
    specs = oews_specs()
    ids = _ids(specs)
    # national, all-industry, Computer & Mathematical (SOC 15-0000), employment (01)
    expected = "OEUN" + "0000000" + "000000" + "150000" + "01"
    assert len(expected) == 25
    assert expected in ids
    assert all(len(s.series_id) == 25 for s in specs)
    assert all(s.annual_only for s in specs)


def test_build_registry_unique_and_large() -> None:
    cfg = FetchConfig(registration_key="x")
    specs = build_registry(cfg)
    ids = [s.series_id for s in specs]
    assert len(ids) == len(set(ids))  # no duplicates
    assert len(ids) > 400
    # respects program selection
    cps_only = build_registry(FetchConfig(registration_key="x", programs=frozenset({Program.CPS})))
    assert all(s.program is Program.CPS for s in cps_only)
