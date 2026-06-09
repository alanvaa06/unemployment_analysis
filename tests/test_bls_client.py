"""Tests for the BLS API client: windowing, parsing, batching, budget."""
from __future__ import annotations

from typing import Any

import pandas as pd
from hypothesis import given
from hypothesis import strategies as st

from unemployment_pipeline.bls_client import FetchReport, fetch_series, year_windows
from unemployment_pipeline.config import FetchConfig, Program, Seasonal, SeriesSpec


class FakeHttpPoster:
    """Records calls; returns a success payload echoing requested series."""

    def __init__(self, missing: set[str] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.missing = missing or set()

    def post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        series = []
        messages = []
        for sid in payload["seriesid"]:
            if sid in self.missing:
                messages.append(f"Series does not exist for Series {sid}")
                series.append({"seriesID": sid, "data": []})
            else:
                series.append({
                    "seriesID": sid,
                    "data": [
                        {"year": "2025", "period": "M12", "periodName": "December",
                         "value": "4.4", "footnotes": [{}]},
                        {"year": "2025", "period": "M11", "periodName": "November",
                         "value": "4.3", "footnotes": [{}]},
                    ],
                })
        return {"status": "REQUEST_SUCCEEDED", "message": messages,
                "Results": {"series": series}}


def _spec(sid: str, start: int = 2020) -> SeriesSpec:
    return SeriesSpec(sid, Program.CPS, sid, Seasonal.SA, start)


def _cfg() -> FetchConfig:
    return FetchConfig(registration_key="testkey")


def test_year_windows_splits_into_20yr_chunks() -> None:
    assert year_windows(1948, 2026) == [(1948, 1967), (1968, 1987), (1988, 2007), (2008, 2026)]


def test_year_windows_single_short_range() -> None:
    assert year_windows(2020, 2025) == [(2020, 2025)]
    assert year_windows(2026, 2020) == []  # start after end


@given(start=st.integers(1900, 2030), span=st.integers(0, 130))
def test_year_windows_invariants(start: int, span: int) -> None:
    end = start + span
    windows = year_windows(start, end)
    assert windows[0][0] == start
    assert windows[-1][1] == end
    for a, b in windows:
        assert b - a <= 19
        assert a <= b
    # contiguous, no gaps
    for (a1, b1), (a2, b2) in zip(windows, windows[1:]):
        assert a2 == b1 + 1


def test_fetch_parses_long_frame() -> None:
    http = FakeHttpPoster()
    df, report = fetch_series([_spec("LNS14000000")], _cfg(), http, current_year=2025)
    assert set(df.columns) >= {"series_id", "year", "period", "date", "value", "footnotes"}
    assert (df["series_id"] == "LNS14000000").all()
    assert df["value"].dtype == float
    dec = df[df["period"] == "M12"].iloc[0]
    assert dec["value"] == 4.4
    assert dec["date"] == pd.Timestamp("2025-12-31")
    assert isinstance(report, FetchReport)
    assert report.requests_made == 1


def test_batching_respects_size_and_budget() -> None:
    http = FakeHttpPoster()
    specs = [_spec(f"S{i:08d}") for i in range(120)]
    cfg = FetchConfig(registration_key="k", daily_request_budget=2)
    df, report = fetch_series(specs, cfg, http, current_year=2025)
    # only 2 requests allowed; each batch <= 50 series
    assert report.requests_made == 2
    assert report.budget_exceeded is True
    assert all(len(c["seriesid"]) <= 50 for c in http.calls)


def test_missing_series_surfaced_in_report() -> None:
    http = FakeHttpPoster(missing={"BADSERIES01"})
    specs = [_spec("LNS14000000"), _spec("BADSERIES01")]
    df, report = fetch_series(specs, _cfg(), http, current_year=2025)
    assert "BADSERIES01" in report.failed
    assert "LNS14000000" not in report.failed
