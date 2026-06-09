"""Verified BLS code lists used to construct series IDs.

Codes traceable to docs/data/bls_series_catalog.md (all verified against the
BLS Public Data API v2).
"""
from __future__ import annotations

# (FIPS, USPS abbreviation, name) — 50 states + DC (11) + Puerto Rico (72).
STATE_FIPS: list[tuple[str, str, str]] = [
    ("01", "AL", "Alabama"), ("02", "AK", "Alaska"), ("04", "AZ", "Arizona"),
    ("05", "AR", "Arkansas"), ("06", "CA", "California"), ("08", "CO", "Colorado"),
    ("09", "CT", "Connecticut"), ("10", "DE", "Delaware"),
    ("11", "DC", "District of Columbia"), ("12", "FL", "Florida"),
    ("13", "GA", "Georgia"), ("15", "HI", "Hawaii"), ("16", "ID", "Idaho"),
    ("17", "IL", "Illinois"), ("18", "IN", "Indiana"), ("19", "IA", "Iowa"),
    ("20", "KS", "Kansas"), ("21", "KY", "Kentucky"), ("22", "LA", "Louisiana"),
    ("23", "ME", "Maine"), ("24", "MD", "Maryland"), ("25", "MA", "Massachusetts"),
    ("26", "MI", "Michigan"), ("27", "MN", "Minnesota"), ("28", "MS", "Mississippi"),
    ("29", "MO", "Missouri"), ("30", "MT", "Montana"), ("31", "NE", "Nebraska"),
    ("32", "NV", "Nevada"), ("33", "NH", "New Hampshire"), ("34", "NJ", "New Jersey"),
    ("35", "NM", "New Mexico"), ("36", "NY", "New York"),
    ("37", "NC", "North Carolina"), ("38", "ND", "North Dakota"), ("39", "OH", "Ohio"),
    ("40", "OK", "Oklahoma"), ("41", "OR", "Oregon"), ("42", "PA", "Pennsylvania"),
    ("44", "RI", "Rhode Island"), ("45", "SC", "South Carolina"),
    ("46", "SD", "South Dakota"), ("47", "TN", "Tennessee"), ("48", "TX", "Texas"),
    ("49", "UT", "Utah"), ("50", "VT", "Vermont"), ("51", "VA", "Virginia"),
    ("53", "WA", "Washington"), ("54", "WV", "West Virginia"),
    ("55", "WI", "Wisconsin"), ("56", "WY", "Wyoming"), ("72", "PR", "Puerto Rico"),
]

# LAUS measure codes (positions 19-20).
LAUS_MEASURES: dict[str, tuple[str, str]] = {
    "03": ("unemployment_rate", "percent"),
    "04": ("unemployment_level", "persons"),
    "05": ("employment_level", "persons"),
    "06": ("labor_force_level", "persons"),
}

# AI-dense / large metros: (CBSA5, anchor state FIPS, name).
AI_METROS: list[tuple[str, str, str]] = [
    ("31080", "06", "Los Angeles-Long Beach-Anaheim, CA"),
    ("41860", "06", "San Francisco-Oakland-Berkeley, CA"),
    ("41940", "06", "San Jose-Sunnyvale-Santa Clara, CA"),
    ("42660", "53", "Seattle-Tacoma-Bellevue, WA"),
    ("12420", "48", "Austin-Round Rock-Georgetown, TX"),
    ("35620", "36", "New York-Newark-Jersey City, NY-NJ-PA"),
    ("14460", "25", "Boston-Cambridge-Newton, MA-NH"),
    ("47900", "11", "Washington-Arlington-Alexandria, DC-VA-MD-WV"),
    ("16980", "17", "Chicago-Naperville-Elgin, IL-IN-WI"),
    ("19100", "48", "Dallas-Fort Worth-Arlington, TX"),
    ("26420", "48", "Houston-The Woodlands-Sugar Land, TX"),
    ("12060", "13", "Atlanta-Sandy Springs-Alpharetta, GA"),
    ("38060", "04", "Phoenix-Mesa-Chandler, AZ"),
    ("19820", "26", "Detroit-Warren-Dearborn, MI"),
]

# CES supersector industry codes (8-digit) -> (label, NAICS-ish, AI-exposed flag).
CES_SUPERSECTORS: list[tuple[str, str, str, bool]] = [
    ("00000000", "Total nonfarm", "", False),
    ("05000000", "Total private", "", False),
    ("50000000", "Information", "51", True),
    ("60000000", "Professional & business services", "54", True),
    ("90000000", "Government", "", False),
]

# JOLTS industry codes (positions 4-9) -> (label, NAICS-ish, AI-exposed flag).
JOLTS_INDUSTRIES: list[tuple[str, str, str, bool]] = [
    ("000000", "Total nonfarm", "", False),
    ("100000", "Total private", "", False),
    ("510000", "Information", "51", True),
    ("540099", "Professional & business services", "54", True),
]

# JOLTS data elements (positions 19-20) -> human label.
JOLTS_ELEMENTS: dict[str, str] = {
    "JO": "job_openings",
    "HI": "hires",
    "QU": "quits",
    "LD": "layoffs_discharges",
    "OS": "other_separations",
    "TS": "total_separations",
}

# JOLTS census-region codes (positions 10-11).
JOLTS_REGIONS: dict[str, str] = {
    "NE": "Northeast", "SO": "South", "MW": "Midwest", "WE": "West",
}

# OEWS AI-exposed occupations: (SOC6, label, NAICS-empty, AI-exposed flag).
AI_SOC: list[tuple[str, str, bool]] = [
    ("150000", "Computer & Mathematical", True),
    ("130000", "Business & Financial Operations", True),
    ("230000", "Legal", True),
    ("270000", "Arts, Design, Entertainment, Sports & Media", True),
    ("430000", "Office & Administrative Support", True),
    ("151252", "Software Developers", True),
    ("152051", "Data Scientists", True),
    ("151211", "Computer Systems Analysts", True),
    ("132011", "Accountants & Auditors", True),
    ("232011", "Paralegals & Legal Assistants", True),
    ("273043", "Writers & Authors", True),
    ("271024", "Graphic Designers", True),
    ("434051", "Customer Service Representatives", True),
    ("439021", "Data Entry Keyers", True),
    ("110000", "Management", False),
    ("290000", "Healthcare Practitioners & Technical", False),
    ("470000", "Construction & Extraction", False),
]
