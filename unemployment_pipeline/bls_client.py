"""BLS Public Data API v2 client: history windowing, batching, parsing, budget."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol, Sequence

import numpy as np
import pandas as pd

from unemployment_pipeline.config import FetchConfig, SeriesSpec

API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
_MAX_SERIES_PER_REQUEST = 50
_MAX_YEARS_PER_REQUEST = 20


class HttpPoster(Protocol):
    """Anything that can POST JSON and return parsed JSON (injected for tests)."""

    def post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class FetchReport:
    """Outcome of a fetch run."""

    requests_made: int = 0
    budget_exceeded: bool = False
    series_returned: int = 0
    failed: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


def year_windows(start: int, end: int) -> list[tuple[int, int]]:
    """Split [start, end] into contiguous chunks of at most 20 years."""
    if start > end:
        return []
    windows: list[tuple[int, int]] = []
    a = start
    while a <= end:
        windows.append((a, min(a + _MAX_YEARS_PER_REQUEST - 1, end)))
        a += _MAX_YEARS_PER_REQUEST
    return windows


def _period_end_date(year: int, period: str) -> Optional[pd.Timestamp]:
    """Map a BLS period code to a period-end Timestamp."""
    if period == "M13" or period == "A01":  # annual average / annual
        return pd.Timestamp(year=year, month=12, day=31)
    if period.startswith("M"):
        month = int(period[1:])
        if 1 <= month <= 12:
            return pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
        return None
    if period.startswith("Q"):
        q = int(period[1:])
        return pd.Timestamp(year=year, month=q * 3, day=1) + pd.offsets.MonthEnd(0)
    return None


def _to_float(raw: str) -> float:
    try:
        return float(raw)
    except (ValueError, TypeError):
        return float(np.nan)


def _chunk(items: Sequence[SeriesSpec], size: int) -> list[list[SeriesSpec]]:
    return [list(items[i:i + size]) for i in range(0, len(items), size)]


def fetch_series(
    specs: Sequence[SeriesSpec],
    config: FetchConfig,
    http: HttpPoster,
    current_year: Optional[int] = None,
    start_year_override: Optional[int] = None,
) -> tuple[pd.DataFrame, FetchReport]:
    """Fetch all specs over their full history via batched, windowed API calls.

    ``start_year_override`` lets the cache request only a recent window.
    """
    end_year = current_year if current_year is not None else datetime.now().year
    report = FetchReport()
    rows: list[dict[str, Any]] = []
    returned_ids: set[str] = set()

    for batch in _chunk(specs, _MAX_SERIES_PER_REQUEST):
        batch_start = (
            start_year_override
            if start_year_override is not None
            else min(s.history_start_year for s in batch)
        )
        for win_start, win_end in year_windows(batch_start, end_year):
            if report.requests_made >= config.daily_request_budget:
                report.budget_exceeded = True
                return _finalize(rows, report, returned_ids)
            payload = {
                "seriesid": [s.series_id for s in batch],
                "startyear": str(win_start),
                "endyear": str(win_end),
                "registrationkey": config.registration_key,
                "annualaverage": True,
            }
            data = http.post(API_URL, payload)
            report.requests_made += 1
            _ingest(data, rows, returned_ids, report)

    # series that never returned any observation are failures
    requested_ids = {s.series_id for s in specs}
    report.failed = sorted(requested_ids - returned_ids)
    return _finalize(rows, report, returned_ids)


def _ingest(data: dict[str, Any], rows: list[dict[str, Any]],
            returned_ids: set[str], report: FetchReport) -> None:
    for msg in data.get("message", []) or []:
        if msg and msg not in report.messages:
            report.messages.append(msg)
    results = data.get("Results") or {}
    for series in results.get("series", []) or []:
        sid = series.get("seriesID", "")
        for point in series.get("data", []) or []:
            year = int(point["year"])
            period = point["period"]
            date = _period_end_date(year, period)
            if date is None:
                continue
            returned_ids.add(sid)
            rows.append({
                "series_id": sid,
                "year": year,
                "period": period,
                "date": date,
                "value": _to_float(point.get("value", "")),
                "footnotes": ",".join(
                    f.get("code", "") for f in point.get("footnotes", []) if f.get("code")
                ),
            })


def _finalize(rows: list[dict[str, Any]], report: FetchReport,
              returned_ids: set[str]) -> tuple[pd.DataFrame, FetchReport]:
    columns = ["series_id", "year", "period", "date", "value", "footnotes"]
    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        df["value"] = df["value"].astype(float)
        df = df.sort_values(["series_id", "date"]).reset_index(drop=True)
    report.series_returned = len(returned_ids)
    if not report.failed:
        report.failed = []
    return df, report


class RequestsHttpPoster:
    """Real HTTP poster using ``requests`` with exponential backoff."""

    def __init__(self, max_retries: int = 4, timeout: int = 60) -> None:
        self.max_retries = max_retries
        self.timeout = timeout

    def post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        import requests  # local import keeps unit tests dependency-light

        delay = 2.0
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001 - retry on any transport error
                last_exc = exc
                if attempt < self.max_retries - 1:
                    time.sleep(delay)
                    delay *= 2
        raise RuntimeError(f"BLS API request failed after retries: {last_exc}")
