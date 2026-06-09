"""Loader for live-verified expanded series (produced by the verification workflow).

The JSON file (``data/reference/expanded_series.json``) holds either a list of
records or an object with a ``series`` key. Each record carries a series_id plus
dimension tags; this module turns them into SeriesSpec objects for the registry.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from unemployment_pipeline.config import Program, Seasonal, SeriesSpec

_DEFAULT_PATH = Path("data/reference/expanded_series.json")
_NATIONAL_PROGRAMS = {"CES", "JOLTS", "OEWS"}


def _to_spec(rec: dict[str, Any]) -> SeriesSpec:
    program = Program[rec["program"]]
    geo_level = rec.get("geo_level")
    if geo_level is None and rec["program"] in _NATIONAL_PROGRAMS:
        geo_level = "national"
    return SeriesSpec(
        series_id=rec["series_id"],
        program=program,
        label=rec.get("label", rec["series_id"]),
        seasonal=Seasonal[rec.get("seasonal", "SA")],
        history_start_year=int(rec.get("history_start_year", 1990)),
        geo_level=geo_level,
        geo_code=rec.get("geo_code"),
        geo_name=rec.get("geo_name"),
        industry_naics=rec.get("industry_naics"),
        occupation_soc=rec.get("occupation_soc"),
        education=rec.get("education"),
        demographic=rec.get("demographic"),
        measure=rec.get("measure"),
        unit=rec.get("unit"),
        annual_only=bool(rec.get("annual_only", False)),
    )


def expanded_specs(path: Path = _DEFAULT_PATH) -> list[SeriesSpec]:
    path = Path(path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data["series"] if isinstance(data, dict) else data
    return [_to_spec(r) for r in records]
