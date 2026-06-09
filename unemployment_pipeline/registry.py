"""Assemble the full tagged series universe from program enumerators."""
from __future__ import annotations

from unemployment_pipeline.config import FetchConfig, Program, SeriesSpec
from unemployment_pipeline.programs.ces import ces_specs
from unemployment_pipeline.programs.cps import cps_specs
from unemployment_pipeline.programs.expanded import expanded_specs
from unemployment_pipeline.programs.jolts import jolts_specs
from unemployment_pipeline.programs.laus import laus_specs
from unemployment_pipeline.programs.oews import oews_specs


def build_registry(config: FetchConfig) -> list[SeriesSpec]:
    """Build the deduplicated list of SeriesSpec for the configured programs."""
    specs: list[SeriesSpec] = []
    if Program.CPS in config.programs:
        specs.extend(cps_specs())
    if Program.LAUS in config.programs:
        specs.extend(laus_specs(config.geo_scope))
    if Program.CES in config.programs:
        specs.extend(ces_specs())
    if Program.JOLTS in config.programs:
        specs.extend(jolts_specs())
    if Program.OEWS in config.programs:
        specs.extend(oews_specs())

    # Live-verified expanded series (industries, education distribution, occupation).
    specs.extend(s for s in expanded_specs() if s.program in config.programs)

    seen: set[str] = set()
    unique: list[SeriesSpec] = []
    for spec in specs:
        if spec.series_id not in seen:
            seen.add(spec.series_id)
            unique.append(spec)
    return unique
