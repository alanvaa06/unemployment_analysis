# BLS Unemployment Pipeline — Design Spec (Phase 1)

**Status:** design approved 2026-06-08 (brainstorming). Phase 1 = **data pipeline only** (no report). Report = Phase 2; econometric AI-impact layer = Phase 3.

**Source of truth for series IDs:** `docs/data/bls_series_catalog.md` (all IDs verified against BLS Public Data API v2).

---

## 1. Goal

A re-runnable Python package that fetches the cataloged BLS series via the Public Data API v2, caches them locally (parquet), and emits a **trusted, tidy, well-documented dataset** ready for a downstream interactive report. It must support maximum per-series history, programmatic enumeration of the granular series universe (states, metros, AI-exposed industries & occupations, education, demographics, labor-flow elements), join external AI-exposure indices to BLS occupation/industry codes, and self-validate via data-quality checks.

The unifying question the data must be able to answer later: **has AI taken a toll on US employment/unemployment?** — so the pipeline prioritizes the cuts that detect that (education gradient, AI-exposed industry/occupation employment & labor-demand flows, geography), joined to exposure indices, with a clean pre/post-Nov-2022 baseline.

## 2. Scope

**In scope (Phase 1):**
- Single pure-Python package `unemployment_pipeline/`, no service layer.
- Manual re-run model with delta-aware parquet cache (cheap re-runs; no scheduler).
- Maximum available history per series (multi-request 20-year windowing).
- Geography ceiling: all states + DC + PR (SA+NSA) and all MSAs. Counties/cities fetchable on demand, **not** in the default pull.
- Series families: CPS (LN), LAUS (LA), CES national + SAE state/metro (CE/SM), JOLTS (JT), OEWS national (OE).
- External AI-exposure join: AIOE, GPTs-are-GPTs, plus SOC↔Census-occ / O*NET-SOC / NAICS crosswalks. AEI optional.
- Tidy output tables (parquet) + machine- and human-readable data-quality report.

**Out of scope (Phase 1 — later phases):**
- The interactive HTML/Plotly report (Phase 2).
- Econometric / causal analysis — diff-in-diff, event study (Phase 3).
- Scheduling / automated refresh / webhook (manual re-run only).
- Counties/cities, OEWS state/metro detail (on-demand extensions, not default).
- DOL UI weekly claims, WARN, Challenger, QCEW, BED — flagged as adjacent in the catalog, not built Phase 1.
- Any UI / dashboard / API server.

## 3. Configuration

### `config.py`

```python
class GeoScope(Enum):
    STATES = auto()            # statewide only
    STATES_METROS = auto()     # default: states + all MSAs
    INCLUDE_COUNTIES = auto()  # on-demand extension

class History(Enum):
    MAX = auto()               # default: to each series' start
    YEARS_20 = auto()
    SINCE_2015 = auto()

@dataclass(frozen=True)
class FetchConfig:
    registration_key: str               # from env BLS_API_KEY; never hard-coded
    geo_scope: GeoScope = GeoScope.STATES_METROS
    history: History = History.MAX
    programs: frozenset[Program] = field(default_factory=lambda: frozenset(Program))
    cache_dir: Path = Path("data/cache")
    reference_dir: Path = Path("data/reference")
    quality_dir: Path = Path("data/quality")
    daily_request_budget: int = 450     # < 500 hard BLS cap, leaves headroom
    revision_refetch_months: int = 14   # trailing window refetched on re-run
```

`registration_key` is read from env `BLS_API_KEY` by the CLI/entrypoint; the dataclass stores it but it is never logged or written to disk.

## 4. Series Registry & Enumerators

### `registry.py` + `programs/`

The registry assembles a `list[SeriesSpec]` from declarative sources. Each program module contributes static IDs and/or enumerators. **No flat-file scraping** (bls.gov bot-blocks); enumeration uses verified ID structures + code lists from the catalog.

```python
class Program(Enum):
    CPS = auto(); LAUS = auto(); CES = auto(); JOLTS = auto(); OEWS = auto()

class Seasonal(Enum):
    SA = auto(); NSA = auto()

@dataclass(frozen=True)
class SeriesSpec:
    series_id: str
    program: Program
    label: str
    seasonal: Seasonal
    history_start_year: int          # earliest year to attempt (for windowing)
    # dimension tags (Optional where N/A):
    geo_level: Optional[str] = None  # "national"|"state"|"metro"
    geo_code: Optional[str] = None   # FIPS or CBSA
    geo_name: Optional[str] = None
    industry_naics: Optional[str] = None
    occupation_soc: Optional[str] = None
    education: Optional[str] = None
    demographic: Optional[str] = None
    measure: Optional[str] = None    # "unemployment_rate"|"hires_level"|...
    unit: Optional[str] = None       # "percent"|"persons"|"dollars"|"index"
    annual_only: bool = False        # OEWS
```

**Program enumerators:**
- `cps.py` — static verified LN IDs from catalog §CPS: headline (6), U-1–U-6 (6), education quartet (4, SA+NSA), demographics (age/sex/race ~20), duration/reason/PTER/marginal (~20). ~120 series.
- `laus.py` — `LA{S|U}ST{FIPS2}…{MM}` over 53 FIPS × {SA,NSA} × {03,04,05,06}; plus `LAUMT{FIPS2}{CBSA5}…{MM}` over the MSA list (NSA) × 4 measures. State FIPS list and MSA→CBSA list are module constants. ~2,000 series.
- `ces.py` — national `CE{S|U}{SS}{datatype}` over supersectors × {01,02,03,06,11} × {SA,NSA}; SAE `SM…` for total-nonfarm + Information(50) + PBS(60) over 53 states (SA) and the AI-dense metro list. ~450 series.
- `jolts.py` — `JT{S|U}{industry}{region}00000…{EL}{R|L}` over elements {JO,HI,TS,QU,LD,OS} × {L,R} × industries (12) × {national + NE/SO/MW/WE} × {SA,NSA where published}. ~220 series.
- `oews.py` — national `OEUN0000000000{soc6}{datatype}` for the AI-exposed SOC watch-list (5 major groups + ~20 detailed children) × {01 employment, 04 mean wage, 13 median wage}. Annual, `annual_only=True`. ~75 series.

**Total default pull ≈ 2,800 series.** At 50/request that is ~56 requests per 20-yr window; with per-program windowing the first full pull is **≈ 250–350 requests** (well under 500/day). Re-runs hit cache → only the trailing-14-month refetch (~60 requests).

## 5. BLS API Client

### `bls_client.py`

```python
def fetch_series(
    specs: Sequence[SeriesSpec],
    config: FetchConfig,
    http: HttpPoster,           # injected (Protocol) — real requests in prod, fake in tests
) -> tuple[pd.DataFrame, FetchReport]:
    """Returns (observations_long, report). Pure orchestration over http."""
```

- **Endpoint:** `POST https://api.bls.gov/publicAPI/v2/timeseries/data/`.
- **Batching:** ≤50 series per request.
- **Max-history windowing:** v2 caps 20 years/request. For each batch, iterate 20-year windows `[start, start+19]` from `min(history_start_year)` of the batch to the current year; **skip windows entirely before a series' start**. Group series sharing a window range to minimize calls.
- **Request budget:** count requests; if a full pull would exceed `daily_request_budget`, fetch greedily up to the budget, persist progress to cache, and emit a `BudgetExceeded` note in the report instructing the user to re-run next day (cache resumes where it left off). Never silently truncate.
- **Retry/backoff:** exponential backoff on HTTP 429/5xx; cap retries; surface BLS JSON `status`/`message` (e.g. `"Series does not exist"`, daily-threshold messages) into the report rather than crashing.
- **Parse:** flatten JSON to long rows `series_id, year, period, period_name, value, footnote_codes`; derive `date` = period end (M01→Jan, M13→annual avg flagged, A01→annual, Q→quarter end). Coerce `value` to float (`-`/blank → NaN).
- **`HttpPoster` Protocol:** `post(url, json) -> dict`. Injected for testability (no live calls in unit tests).

## 6. Cache Layer

### `cache.py`

- `observations.parquet` keyed by `(series_id, date)`. Delta-aware:
  - Load cache; for each requested series compute missing range `(cached_max_date+1 → now)`.
  - **Revision-aware:** always also refetch the trailing `revision_refetch_months` (covers BLS 2-month rolling revisions + January annual benchmark + LAUS spring benchmark). Overwrite those rows on merge.
  - Merge: concat, dedupe on `(series_id, date)` keeping newest fetch, sort, rewrite parquet.
- `latest_flag`: per series, mark the max-date row `True` for fast "current value" reads downstream.
- Annual (OEWS) series cached in the same store with `period=A01`; flagged `annual_only` in metadata.

## 7. Crosswalks & Exposure Join

### `crosswalks.py`
Download (once, cached to `reference_dir`) and normalize:
- **Census 2018 Occupation Code List + SOC crosswalk** (`census.gov` .xlsx) → `crosswalk_census_soc.parquet` (`census_occ, soc6, title`). The bridge CPS occupation codes need.
- **O*NET-SOC → SOC** via 6-digit truncation (no download; documented rule).
- **NAICS ↔ CES/JOLTS industry codes** → small hand-verified map module constant (from catalog supersector tables).

### `exposure.py`
Download (cached) and normalize to SOC6 / NAICS keys:
- **AIOE** — `github.com/AIOE-Data/AIOE` `AIOE_DataAppendix.xlsx` + `Language Modeling AIOE and AIIE.xlsx` → `exposure_occupation` (`soc6, aioe, aioe_langmod`) and `exposure_industry` (`naics, aiie, aiie_langmod`).
- **GPTs-are-GPTs** — `github.com/openai/GPTs-are-GPTs` `data/occ_level.csv` → collapse O*NET-SOC→SOC6 → `soc6, gpts_alpha, gpts_beta, gpts_gamma`.
- **AEI (optional)** — HuggingFace `Anthropic/EconomicIndex` → adoption covariate by SOC/state (Phase-1 optional, behind a flag).
- Hosts (raw.githubusercontent.com, census.gov) are fetchable; on fetch failure, emit a clear "manual download to `reference/`" instruction (graceful degradation, not a crash).

Output: `exposure_occupation.parquet`, `exposure_industry.parquet` — joinable to `series_meta` on `occupation_soc` / `industry_naics`.

## 8. Datasets (output contract — Phase-2 input)

### `datasets.py` → writes to `cache_dir`:
| File | Grain | Columns |
|---|---|---|
| `observations.parquet` | series × date | `series_id, date, year, period, value, footnotes, latest_flag` |
| `series_meta.parquet` | series | all `SeriesSpec` tag fields + `history_start, unit, seasonal` |
| `exposure_occupation.parquet` | SOC6 | `soc6, aioe, aioe_langmod, gpts_alpha, gpts_beta, gpts_gamma` |
| `exposure_industry.parquet` | NAICS | `naics, aiie, aiie_langmod` |
| `crosswalk_census_soc.parquet` | census_occ | `census_occ, soc6, title` |

**Determinism:** same config + same cache state → byte-identical parquet (sorted keys, no timestamps inside data). Fetch metadata (run time, request count) goes only to the quality report.

## 9. Data-Quality Checks (the "is data trusted?" gate)

### `quality.py` → `quality/quality_report.{json,md}`
- **Coverage:** % of requested series returning ≥1 observation; list every missing/"does not exist" series. **Fail** if any series in a `REQUIRED_CORE` allowlist is missing; expected-missing IDs live in a documented exception list.
- **Identity checks:** JOLTS `TS ≈ QU + LD + OS` (±2k level / ±0.1pp); `U-3 == LNS14000000`; labor force `≈ employed + unemployed`. Report violations.
- **Freshness:** latest period per program within tolerance (CPS ≤2mo, CES ≤2mo, LAUS ≤2mo, JOLTS ≤3mo, OEWS ≤18mo). Warn if stale.
- **Gaps:** flag interior missing monthly periods per series.
- **SA/NSA presence:** confirm both where the catalog says both exist.
- **Join completeness:** % of occupation series matched to an exposure score; % industry matched; list unmatched SOC/NAICS.
- Exit code non-zero on any **Fail** (clear messages); warnings don't fail the run.

## 10. Public API & CLI

```python
from unemployment_pipeline import fetch_all, load_dataset
report = fetch_all(config)                      # fetch+cache+join+quality; returns QualityReport
obs = load_dataset("observations")              # convenience parquet readers
```

```
python -m unemployment_pipeline fetch \
    [--geo states-metros|states|include-counties] \
    [--history max|20y|since-2015] \
    [--programs cps,laus,ces,jolts,oews] \
    [--no-exposure] [--budget 450]
# key from env BLS_API_KEY (required)
python -m unemployment_pipeline quality   # re-run checks on cached data, print report
```

## 11. Testing (per `docs/references/python_best_practices.md`)

- **pytest**, Arrange-Act-Assert, fixtures. Full type hints; **mypy strict** (`--disallow-untyped-defs`, `--no-implicit-optional`). black + flake8.
- **No live API in unit tests** — `HttpPoster` Protocol injected with recorded JSON fixtures (real BLS payloads captured once). One opt-in integration test hits the live API (marked `@pytest.mark.integration`, needs key).
- **Coverage targets:** `test_bls_client` (windowing math: a 1948-start series yields exactly 4 windows, none before start; JSON→long parse; budget cutoff; error-status surfacing). `test_cache` (delta range, trailing-14mo refetch overwrites revised rows, dedupe keeps newest). `test_registry` (enumerator counts; every generated ID matches the program's char-length & prefix). `test_exposure` (O*NET-SOC→SOC6 collapse; join completeness). `test_quality` (identity check catches an injected violation; coverage Fail on missing REQUIRED_CORE).
- **Hypothesis:** window generator — any `(start_year, current_year)` → windows are contiguous, ≤20yr each, cover `[start, current]`, none precede start. Cache merge — any two overlapping frames → no duplicate `(series_id, date)`, newest wins.
- **Mutation (mutmut):** target `bls_client` windowing and `cache` merge — the suite must catch logic mutants.

## 12. File Layout

```
unemployment_pipeline/
├── __init__.py          # fetch_all, load_dataset
├── config.py            # enums + FetchConfig
├── registry.py          # assemble SeriesSpec list
├── programs/
│   ├── cps.py  laus.py  ces.py  jolts.py  oews.py
│   └── constants.py     # state FIPS, MSA/CBSA list, AI-metro list, supersector/SOC maps
├── bls_client.py        # HttpPoster Protocol, fetch_series, windowing, parse
├── cache.py             # delta + revision-aware parquet store
├── crosswalks.py        # Census/O*NET/NAICS loaders
├── exposure.py          # AIOE, GPTs-are-GPTs, (AEI)
├── datasets.py          # assemble + write output contract
├── quality.py           # checks + report
└── cli.py               # argparse; __main__.py delegates
tests/                   # one file per module + fixtures/ (recorded JSON)
data/  cache/  reference/  quality/
pyproject.toml           # deps + black/flake8/mypy config
```

## 13. Dependencies
`requests, pandas, pyarrow, openpyxl` (read .xlsx), `pytest, hypothesis, mutmut, mypy, black, flake8`. No heavy new deps. Python 3.11+.

## 14. Limitations
- **OEWS** is an annual lagged snapshot, not a time series — stored separately, lag-flagged; SOC-vintage breaks (2010→2018) documented, not reconciled Phase 1.
- **Sub-state is residence-based (LAUS) and NSA below state** — geography/industry attribution must pair with establishment-based CES later.
- **Exposure indices disagree** (Stanford payroll vs Yale CPS) — Phase 1 only *provides the joins*; interpretation deferred to Phase 3, which must report multiple indices/outcomes.
- **Subgroup noise** (education/occupation) — raw values cached; smoothing is a Phase-2 presentation concern.
- **BLS revisions** — the cache reflects the latest vintage; point-in-time/vintage history is not retained.

## 15. Acceptance Criteria
- [ ] `BLS_API_KEY` env set → `python -m unemployment_pipeline fetch` runs end-to-end, writes `observations.parquet`, `series_meta.parquet`, exposure + crosswalk parquet, and `quality_report.{json,md}`.
- [ ] Default pull covers all states+DC+PR (SA+NSA, 4 measures), all MSAs, CES AI-sectors national+metro, full JOLTS elements, CPS education/demographic/duration, OEWS national AI-exposed occupations.
- [ ] Max-history verified: headline UR `LNS14000000` returns data back to 1948 via multi-window fetch.
- [ ] Re-run is cheap: second run fetches only trailing-14-month window + new periods (request count logged, ≫ smaller than first run).
- [ ] Quality report: coverage ≥ targeted %, JOLTS identity holds, freshness within tolerance; run fails loudly if a REQUIRED_CORE series is missing.
- [ ] Exposure join: ≥90% of OEWS AI-exposed SOC6 matched to AIOE & GPTs scores; unmatched listed.
- [ ] Test suite green: ≥5 module test files, ≥30 tests, mypy strict clean, hypothesis invariants pass.
- [ ] No secrets on disk/logs; `BLS_API_KEY` only from env.

## 16. Future Work
- Phase 2: interactive HTML/Plotly report (headline dashboard, education gradient, AI-exposed industry/occupation divergence, pre/post-Nov-2022 event visuals).
- Phase 3: econometric layer (diff-in-diff / event study, continuous exposure × post-2022, parallel-trends validation, multiple indices & outcome sources).
- On-demand extensions: counties/cities, OEWS state/metro, QCEW, DOL UI weekly claims, BED, Challenger AI-layoff tracker.
```

---
*Compiled 2026-06-08. Series universe defined by `docs/data/bls_series_catalog.md`.*
