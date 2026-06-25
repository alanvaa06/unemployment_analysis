"""Translation lookup and coverage."""
import json
from pathlib import Path

from dashboard import i18n


def test_t_es_translates_known_string():
    assert i18n.t("Unemployment rate", "es") == "Tasa de desempleo"


def test_t_en_is_identity():
    assert i18n.t("Unemployment rate", "en") == "Unemployment rate"
    assert i18n.t("anything at all", "en") == "anything at all"


def test_t_unknown_falls_back_to_input():
    assert i18n.t("a string with no translation", "es") == "a string with no translation"


def test_t_default_lang_is_es():
    assert i18n.t("Job openings") == "Vacantes"


def test_table_has_no_empty_spanish():
    data = json.loads(
        (Path(i18n.__file__).parent / "translations.json").read_text(encoding="utf-8"))
    assert data, "translations.json is empty"
    assert all(row["spanish"].strip() for row in data), "an entry has empty Spanish"


def test_critical_terms_present():
    for s in ["Unemployment rate", "Job openings", "Findings",
              "Has AI taken a toll on jobs?", "Where the jobs went"]:
        assert i18n.t(s, "es") != s, f"missing translation for {s!r}"
