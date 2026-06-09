"""End-to-end orchestration test with a fake HTTP poster."""
from __future__ import annotations

from datetime import date
from typing import Any

from unemployment_pipeline import fetch_all, load_dataset
from unemployment_pipeline.config import FetchConfig, Program


class FakeHttpPoster:
    def __init__(self) -> None:
        self.calls = 0

    def post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        series = [{
            "seriesID": sid,
            "data": [{"year": "2025", "period": "M12", "periodName": "December",
                      "value": "4.4", "footnotes": [{}]}],
        } for sid in payload["seriesid"]]
        return {"status": "REQUEST_SUCCEEDED", "message": [], "Results": {"series": series}}


def test_fetch_all_end_to_end_cps_only(tmp_path) -> None:
    cfg = FetchConfig(
        registration_key="k",
        programs=frozenset({Program.CPS}),
        cache_dir=tmp_path / "cache",
        reference_dir=tmp_path / "ref",
        quality_dir=tmp_path / "q",
    )
    fake = FakeHttpPoster()
    report = fetch_all(cfg, http=fake, current_year=2025, today=date(2026, 1, 1))

    # CPS-only registry: required-core is filtered to CPS series, all returned -> pass
    assert report.passed is True
    obs = load_dataset("observations", cfg.cache_dir)
    assert not obs.empty
    assert "LNS14000000" in set(obs["series_id"])
    assert (cfg.cache_dir / "series_meta.parquet").exists()
    assert (cfg.quality_dir / "quality_report.md").exists()


def test_rerun_uses_cache_and_is_cheaper(tmp_path) -> None:
    cfg = FetchConfig(
        registration_key="k",
        programs=frozenset({Program.CPS}),
        cache_dir=tmp_path / "cache",
        reference_dir=tmp_path / "ref",
        quality_dir=tmp_path / "q",
    )
    first = FakeHttpPoster()
    fetch_all(cfg, http=first, current_year=2025, today=date(2026, 1, 1))
    second = FakeHttpPoster()
    fetch_all(cfg, http=second, current_year=2025, today=date(2026, 1, 1))
    # second run: all series warm -> only a short trailing window, fewer requests
    assert second.calls < first.calls
