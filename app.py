"""Local web app: serve the dashboard, refresh data from BLS, export analysis.

Run:  python app.py   then open  http://127.0.0.1:8765
The refresh and export buttons in the dashboard call this server's /api endpoints.
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file

from dashboard.export import build_workbook
from dashboard.interactive_build import build_interactive
from unemployment_pipeline.cache import ParquetCache
from unemployment_pipeline.config import FetchConfig

load_dotenv()
app = Flask(__name__)

CACHE = Path("data/cache")
OUT = Path("output/dashboard.html")
REFRESH_GUARD_HOURS = 6.0


def _latest_month() -> str | None:
    obs = ParquetCache(CACHE).load()
    return None if obs.empty else obs["date"].max().strftime("%Y-%m")


def _last_refresh_age_hours() -> float | None:
    p = CACHE / "observations.parquet"
    return (time.time() - p.stat().st_mtime) / 3600 if p.exists() else None


@app.get("/")
def index():
    if not OUT.exists():
        build_interactive()
    return send_file(OUT.resolve())


@app.get("/api/status")
def status():
    age = _last_refresh_age_hours()
    return jsonify(latest_month=_latest_month(),
                   age_hours=None if age is None else round(age, 1),
                   fresh=(age is not None and age < REFRESH_GUARD_HOURS))


@app.post("/api/refresh")
def refresh():
    body = request.get_json(silent=True) or {}
    force = bool(body.get("force"))
    key = (body.get("key") or os.environ.get("BLS_API_KEY") or "").strip()
    if not key:
        return jsonify(ok=False, error="No BLS API key. Enter one above, or set BLS_API_KEY in .env."), 400
    age = _last_refresh_age_hours()
    if not force and age is not None and age < REFRESH_GUARD_HOURS:
        return jsonify(ok=False, warning=(
            f"Data was refreshed {age:.1f}h ago. BLS updates these series monthly, so a refresh "
            "now will usually return the same numbers and just spends API quota. Refresh anyway?"),
            age_hours=round(age, 1)), 200
    try:
        from unemployment_pipeline.pipeline import fetch_all
        report = fetch_all(FetchConfig(registration_key=key), today=date.today())
        build_interactive()
        obs = ParquetCache(CACHE).load()
        return jsonify(ok=True, series=int(obs["series_id"].nunique()), rows=int(len(obs)),
                       latest_month=_latest_month(), quality_passed=bool(report.passed))
    except Exception as exc:  # surface the failure to the UI
        return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500


@app.get("/api/export/data.xlsx")
def export_xlsx():
    base = request.args.get("base", "2022-11")
    compare = request.args.get("compare", "2026-05")
    out = Path("output/_export.xlsx")
    build_workbook(out, base=base, compare=compare, cache_dir=CACHE)
    return send_file(out.resolve(), as_attachment=True, download_name="ai_jobs_analysis.xlsx")


def main() -> None:
    port = int(os.environ.get("PORT", "8765"))
    print(f"Serving dashboard at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
