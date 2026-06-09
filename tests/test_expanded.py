"""Tests for the expanded-series JSON loader."""
from __future__ import annotations

import json

from unemployment_pipeline.config import Program, Seasonal
from unemployment_pipeline.programs.expanded import expanded_specs


def test_missing_file_returns_empty(tmp_path) -> None:
    assert expanded_specs(tmp_path / "nope.json") == []


def test_loads_specs_with_tags(tmp_path) -> None:
    path = tmp_path / "expanded.json"
    path.write_text(json.dumps({"series": [
        {"series_id": "CES4142000001", "program": "CES", "label": "Wholesale trade",
         "seasonal": "SA", "history_start_year": 1990, "measure": "ces_01",
         "unit": "persons_thousands", "industry_naics": "42"},
        {"series_id": "LNS12027662", "program": "CPS", "label": "Employment, bachelors+",
         "seasonal": "SA", "history_start_year": 1992, "measure": "employment_level",
         "education": "bachelors_plus", "unit": "persons"},
    ]}), encoding="utf-8")
    specs = expanded_specs(path)
    assert len(specs) == 2
    ces = [s for s in specs if s.series_id == "CES4142000001"][0]
    assert ces.program is Program.CES
    assert ces.seasonal is Seasonal.SA
    assert ces.geo_level == "national"          # defaulted for CES
    assert ces.industry_naics == "42"
    cps = [s for s in specs if s.series_id == "LNS12027662"][0]
    assert cps.education == "bachelors_plus"
    assert cps.measure == "employment_level"


def test_accepts_bare_list(tmp_path) -> None:
    path = tmp_path / "list.json"
    path.write_text(json.dumps([
        {"series_id": "JTS510000000000000QUL", "program": "JOLTS", "label": "Info quits",
         "seasonal": "SA", "history_start_year": 2000, "measure": "jolts_quits_level"},
    ]), encoding="utf-8")
    specs = expanded_specs(path)
    assert len(specs) == 1
    assert specs[0].geo_level == "national"
