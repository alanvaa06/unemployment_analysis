"""Build-time i18n. English source strings map to Spanish via translations.json.

t(s, "en") is identity; t(s, "es") returns the Spanish or falls back to s.
The English string is its own key — no invented IDs.
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA = json.loads(
    (Path(__file__).parent / "translations.json").read_text(encoding="utf-8"))

ES: dict[str, str] = {row["english"]: row["spanish"] for row in _DATA}


def t(s: str, lang: str = "es") -> str:
    if lang == "en":
        return s
    return ES.get(s, s)
