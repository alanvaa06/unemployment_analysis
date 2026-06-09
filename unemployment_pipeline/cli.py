"""Command-line entry point for the pipeline."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from unemployment_pipeline.cache import ParquetCache
from unemployment_pipeline.config import FetchConfig, GeoScope, History, Program
from unemployment_pipeline.pipeline import fetch_all
from unemployment_pipeline.quality import DEFAULT_REQUIRED_CORE, run_quality_checks

_GEO = {"states": GeoScope.STATES, "states-metros": GeoScope.STATES_METROS,
        "include-counties": GeoScope.INCLUDE_COUNTIES}
_HIST = {"max": History.MAX, "20y": History.YEARS_20, "since-2015": History.SINCE_2015}


def _require_key() -> str:
    load_dotenv()
    key = os.environ.get("BLS_API_KEY", "").strip()
    if not key:
        print("ERROR: BLS_API_KEY not set (put it in .env).", file=sys.stderr)
        raise SystemExit(2)
    return key


def _build_config(args: argparse.Namespace, key: str) -> FetchConfig:
    programs = (
        frozenset(Program[p.strip().upper()] for p in args.programs.split(","))
        if args.programs else frozenset(Program)
    )
    return FetchConfig(
        registration_key=key,
        geo_scope=_GEO[args.geo],
        history=_HIST[args.history],
        programs=programs,
        daily_request_budget=args.budget,
    )


def _cmd_fetch(args: argparse.Namespace) -> int:
    key = _require_key()
    config = _build_config(args, key)
    report = fetch_all(config, today=date.today())
    obs = ParquetCache(config.cache_dir).load()
    print(f"Series cached: {obs['series_id'].nunique()} | rows: {len(obs)}")
    print(report.to_markdown())
    return 0 if report.passed else 1


def _cmd_quality(args: argparse.Namespace) -> int:
    cache = ParquetCache(Path("data/cache"))
    obs = cache.load()
    if obs.empty:
        print("No cached data. Run `fetch` first.", file=sys.stderr)
        return 2
    report = run_quality_checks(obs, required_core=DEFAULT_REQUIRED_CORE, today=date.today())
    print(report.to_markdown())
    return 0 if report.passed else 1


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1252 and choke on report emoji; force UTF-8.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="unemployment_pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="fetch + cache + validate")
    f.add_argument("--geo", choices=list(_GEO), default="states-metros")
    f.add_argument("--history", choices=list(_HIST), default="max")
    f.add_argument("--programs", default="", help="comma list: cps,laus,ces,jolts,oews")
    f.add_argument("--budget", type=int, default=450)
    f.set_defaults(func=_cmd_fetch)

    q = sub.add_parser("quality", help="re-run quality checks on cached data")
    q.set_defaults(func=_cmd_quality)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
