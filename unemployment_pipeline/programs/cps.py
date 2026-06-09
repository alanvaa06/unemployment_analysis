"""CPS national labor-force series (LN). Static verified IDs from the catalog."""
from __future__ import annotations

from unemployment_pipeline.config import Program, Seasonal, SeriesSpec

# (series_id, label, start_year, measure, education, demographic)
_HEADLINE: list[tuple[str, str, int, str]] = [
    ("LNS14000000", "Unemployment rate (U-3)", 1948, "unemployment_rate"),
    ("LNS11000000", "Civilian labor force level", 1948, "labor_force_level"),
    ("LNS12000000", "Employment level", 1948, "employment_level"),
    ("LNS13000000", "Unemployment level", 1948, "unemployment_level"),
    ("LNS11300000", "Labor force participation rate", 1948, "lfpr"),
    ("LNS12300000", "Employment-population ratio", 1948, "emp_pop_ratio"),
]

_UMEASURES: list[tuple[str, str, int, str]] = [
    ("LNS13025670", "U-1 (unemployed 15+ wks, % LF)", 1948, "u1"),
    ("LNS14023621", "U-2 (job losers, % LF)", 1967, "u2"),
    ("LNS13327707", "U-4 (+ discouraged)", 1994, "u4"),
    ("LNS13327708", "U-5 (+ marginally attached)", 1994, "u5"),
    ("LNS13327709", "U-6 (+ marginally attached + PTER)", 1994, "u6"),
]

_DURATION_REASON: list[tuple[str, str, int, str]] = [
    ("LNS13008275", "Mean weeks unemployed", 1948, "mean_weeks"),
    ("LNS13008276", "Median weeks unemployed", 1967, "median_weeks"),
    ("LNS13008636", "Unemployed 27+ weeks (level)", 1948, "long_term_level"),
    ("LNS13092836", "Unemployed 27+ weeks (% of LF)", 2011, "long_term_share"),
    ("LNS13023621", "Job losers (level)", 1967, "job_losers"),
    ("LNS13023705", "Job leavers (level)", 1967, "job_leavers"),
    ("LNS13023557", "Reentrants (level)", 1967, "reentrants"),
    ("LNS13023569", "New entrants (level)", 1967, "new_entrants"),
]

# (series_id, label, start_year, education)
_EDUCATION: list[tuple[str, str, int, str]] = [
    ("LNS14027659", "UR: less than high school", 1992, "less_than_hs"),
    ("LNS14027660", "UR: high school, no college", 1992, "high_school"),
    ("LNS14027689", "UR: some college or associate", 1992, "some_college"),
    ("LNS14027662", "UR: bachelor's degree and higher", 1992, "bachelors_plus"),
]

# (series_id, label, start_year, demographic)
_DEMOGRAPHIC: list[tuple[str, str, int, str]] = [
    ("LNS14000012", "UR: 16-19 years", 1948, "age_16_19"),
    ("LNS14000060", "UR: 25-54 years (prime age)", 1948, "age_25_54"),
    ("LNS14024230", "UR: 55 years and over", 1948, "age_55_plus"),
    ("LNS14000025", "UR: men 20+", 1948, "men"),
    ("LNS14000026", "UR: women 20+", 1948, "women"),
    ("LNS14000003", "UR: White", 1954, "white"),
    ("LNS14000006", "UR: Black or African American", 1972, "black"),
    ("LNS14000009", "UR: Hispanic or Latino", 1973, "hispanic"),
    ("LNS14032183", "UR: Asian", 2003, "asian"),
]


def cps_specs() -> list[SeriesSpec]:
    """All CPS national LN series (seasonally adjusted)."""
    specs: list[SeriesSpec] = []
    for sid, label, start, measure in _HEADLINE + _UMEASURES + _DURATION_REASON:
        unit = "percent" if "rate" in measure or measure.startswith("u") or "share" in measure or "lfpr" in measure or "ratio" in measure else "persons_or_weeks"
        specs.append(SeriesSpec(sid, Program.CPS, label, Seasonal.SA, start, measure=measure, unit=unit))
    for sid, label, start, education in _EDUCATION:
        specs.append(SeriesSpec(sid, Program.CPS, label, Seasonal.SA, start,
                                measure="unemployment_rate", education=education, unit="percent"))
    for sid, label, start, demo in _DEMOGRAPHIC:
        specs.append(SeriesSpec(sid, Program.CPS, label, Seasonal.SA, start,
                                measure="unemployment_rate", demographic=demo, unit="percent"))
    return specs
