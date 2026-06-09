"""Occupation/industry code crosswalks (SOC backbone)."""
from __future__ import annotations

import re


def onet_to_soc6(code: str) -> str:
    """Collapse an O*NET-SOC or SOC code to 6 digits (first 6 numeric chars)."""
    digits = re.sub(r"\D", "", str(code))
    return digits[:6]
