"""Tests for config enums and dataclasses."""
from __future__ import annotations

import dataclasses
from enum import Enum

import pytest

from unemployment_pipeline.config import (
    FetchConfig,
    GeoScope,
    History,
    Program,
    Seasonal,
    SeriesSpec,
)


def test_enums_are_enums() -> None:
    assert issubclass(Program, Enum)
    assert issubclass(Seasonal, Enum)
    assert issubclass(GeoScope, Enum)
    assert issubclass(History, Enum)
    assert {p.name for p in Program} == {"CPS", "LAUS", "CES", "JOLTS", "OEWS"}
    assert {s.name for s in Seasonal} == {"SA", "NSA"}


def test_seriesspec_is_frozen_and_tagged() -> None:
    spec = SeriesSpec(
        series_id="LNS14000000",
        program=Program.CPS,
        label="Unemployment rate",
        seasonal=Seasonal.SA,
        history_start_year=1948,
        measure="unemployment_rate",
        unit="percent",
    )
    assert spec.series_id == "LNS14000000"
    assert spec.geo_level is None  # default
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.label = "changed"  # type: ignore[misc]


def test_fetchconfig_defaults() -> None:
    cfg = FetchConfig(registration_key="abc123")
    assert cfg.geo_scope is GeoScope.STATES_METROS
    assert cfg.history is History.MAX
    assert cfg.daily_request_budget == 450
    assert cfg.revision_refetch_months == 14
    assert Program.CPS in cfg.programs
    # frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.daily_request_budget = 10  # type: ignore[misc]
