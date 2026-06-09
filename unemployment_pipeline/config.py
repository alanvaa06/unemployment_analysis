"""Configuration enums and immutable dataclasses for the BLS pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional


class Program(Enum):
    """BLS survey programs covered by the pipeline."""

    CPS = auto()
    LAUS = auto()
    CES = auto()
    JOLTS = auto()
    OEWS = auto()


class Seasonal(Enum):
    """Seasonal-adjustment flavour of a series."""

    SA = auto()
    NSA = auto()


class GeoScope(Enum):
    """Geographic granularity ceiling for the default pull."""

    STATES = auto()
    STATES_METROS = auto()
    INCLUDE_COUNTIES = auto()


class History(Enum):
    """How far back to fetch per series."""

    MAX = auto()
    YEARS_20 = auto()
    SINCE_2015 = auto()


@dataclass(frozen=True)
class SeriesSpec:
    """A single BLS series plus its dimension tags (metadata)."""

    series_id: str
    program: Program
    label: str
    seasonal: Seasonal
    history_start_year: int
    geo_level: Optional[str] = None
    geo_code: Optional[str] = None
    geo_name: Optional[str] = None
    industry_naics: Optional[str] = None
    occupation_soc: Optional[str] = None
    education: Optional[str] = None
    demographic: Optional[str] = None
    measure: Optional[str] = None
    unit: Optional[str] = None
    annual_only: bool = False


def _default_programs() -> frozenset[Program]:
    return frozenset(Program)


@dataclass(frozen=True)
class FetchConfig:
    """Run configuration. ``registration_key`` comes from env BLS_API_KEY."""

    registration_key: str
    geo_scope: GeoScope = GeoScope.STATES_METROS
    history: History = History.MAX
    programs: frozenset[Program] = field(default_factory=_default_programs)
    cache_dir: Path = Path("data/cache")
    reference_dir: Path = Path("data/reference")
    quality_dir: Path = Path("data/quality")
    daily_request_budget: int = 450
    revision_refetch_months: int = 14
