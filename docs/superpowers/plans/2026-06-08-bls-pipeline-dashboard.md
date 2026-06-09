# BLS Pipeline + AI-Impact Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:test-driven-development per task. Steps use checkbox (`- [ ]`) syntax. Build order is dependency-ordered; modules are TDD'd (red→green→refactor) before the live fetch and dashboard.

**Goal:** Ship a re-runnable BLS data pipeline that fetches the cataloged unemployment/workforce series, caches them, joins AI-exposure indices, self-validates — then a light interactive HTML dashboard that visualizes whether AI has taken a toll on jobs.

**Architecture:** Declarative tagged series registry → generic windowing/batching API client (injected `HttpPoster`) → delta+revision-aware parquet cache → exposure/crosswalk join → quality gate → tidy parquet output contract → Plotly dashboard (single self-contained light HTML). Spec: `docs/superpowers/specs/2026-06-08-bls-unemployment-pipeline-design.md`.

**Tech Stack:** Python 3.14, pandas, pyarrow, requests, python-dotenv, openpyxl, plotly; pytest + hypothesis (TDD); all deps already installed.

**Registry scope for first runnable build:** curated-but-rich — national headline + U1–U6 + education + duration; all 50+DC+PR states (SA+NSA, 4 measures); ~12 AI-dense metros; CES Information(50)/PBS(60)/total-nonfarm national + AI metros; full JOLTS elements national + 4 regions + Information/PBS; OEWS national AI-exposed occupations. Architecture supports expanding to the full ~2,800-series universe by extending `programs/` constants — no code change elsewhere.

---

## File Structure

```
unemployment_pipeline/
├── __init__.py        # public API: fetch_all(), load_dataset()
├── config.py          # Program/Seasonal/GeoScope/History enums + FetchConfig + SeriesSpec
├── programs/
│   ├── constants.py   # STATE_FIPS, AI_METROS (CBSA), CES_SUPERSECTORS, JOLTS_*, AI_SOC
│   ├── cps.py         # cps_specs() -> list[SeriesSpec]
│   ├── laus.py        # laus_specs(geo_scope) -> list[SeriesSpec]
│   ├── ces.py         # ces_specs() -> list[SeriesSpec]
│   ├── jolts.py       # jolts_specs() -> list[SeriesSpec]
│   └── oews.py        # oews_specs() -> list[SeriesSpec]
├── registry.py        # build_registry(config) -> list[SeriesSpec]
├── bls_client.py      # HttpPoster Protocol, year_windows(), fetch_series()
├── cache.py           # ParquetCache: load/merge with revision refetch
├── crosswalks.py      # load_census_soc(), onet_to_soc6()
├── exposure.py        # load_aioe(), load_gpts(), build exposure tables
├── datasets.py        # assemble + write observations/series_meta/exposure parquet
├── quality.py         # run_quality_checks() -> QualityReport (+ md/json writer)
├── cli.py             # argparse: fetch / quality
└── __main__.py        # delegates to cli.main()
dashboard/
├── prepare.py         # pure data-prep: load parquet -> chart-ready frames
├── charts.py          # plotly figure builders (one per chart)
└── build.py           # assemble figures -> single light HTML (impeccable UI shell)
tests/                 # one per module + fixtures/ (recorded BLS JSON, mini xlsx/csv)
data/ cache/ reference/ quality/
pyproject.toml
output/dashboard.html  # final deliverable
```

---

### Task 0: Scaffold

**Files:** Create `pyproject.toml`, `unemployment_pipeline/__init__.py`, `dashboard/__init__.py`, `tests/__init__.py`, `tests/conftest.py`.

- [ ] Create `pyproject.toml` (project name `unemployment_pipeline`, deps listed, pytest config: `testpaths=tests`, `markers=integration`).
- [ ] Create empty package `__init__.py` files.
- [ ] `tests/conftest.py`: loads `.env` via python-dotenv for the opt-in integration test; provides `fixtures_dir` fixture.
- [ ] Run `pytest -q` → expect "no tests ran" (collection works).
- [ ] Commit: `chore: scaffold unemployment_pipeline package`.

---

### Task 1: config.py — enums + SeriesSpec + FetchConfig

**Files:** Create `unemployment_pipeline/config.py`, `tests/test_config.py`.

- [ ] **Test (red):** `Program`, `Seasonal`, `GeoScope`, `History` are Enums; `SeriesSpec(series_id="LNS14000000", program=Program.CPS, label="UR", seasonal=Seasonal.SA, history_start_year=1948)` is frozen (mutating raises `FrozenInstanceError`); `FetchConfig(registration_key="x")` has defaults `geo_scope=STATES_METROS`, `history=MAX`, `daily_request_budget=450`, `revision_refetch_months=14`.
- [ ] Run → fail (module missing).
- [ ] **Green:** implement enums + two frozen dataclasses with full type hints (per spec §3).
- [ ] Run → pass. Commit `feat: config enums + dataclasses`.

---

### Task 2: programs + registry — enumerators

**Files:** Create `programs/constants.py`, `programs/{cps,laus,ces,jolts,oews}.py`, `registry.py`, `tests/test_registry.py`.

- [ ] **Test (red):**
  - `cps_specs()` includes `LNS14000000`, the education quartet (`LNS14027659/60/89/62`), all `seasonal` set.
  - `laus_specs(GeoScope.STATES_METROS)` yields, for every state FIPS, 2 (SA/NSA) × 4 measures = 8 specs; every id matches `^LA[SU]ST\d{13}\d{2}$` length 20; metros present with `^LAUMT` and `geo_level=="metro"`.
  - `jolts_specs()` ids are length 21, start `JT`, include `JTS000000000000000HIL` (hires level) and Information `510000`/PBS `540099`.
  - `ces_specs()` includes `CES5000000001` (Information) and `CES6000000001` (PBS); SM ids length 20.
  - `build_registry(config)` returns unique `series_id`s (no dupes), tagged, count > 400.
- [ ] Run → fail.
- [ ] **Green:** implement constants (STATE_FIPS list incl gaps, AI_METROS CBSA map, supersector codes, JOLTS element/industry/region codes, AI_SOC watch-list) and the `*_specs()` builders + `build_registry` (dedupe by id). IDs built by f-string templates from the catalog.
- [ ] Run → pass. Commit `feat: program enumerators + registry`.

---

### Task 3: bls_client.py — windowing, parse, batching

**Files:** Create `bls_client.py`, `tests/test_bls_client.py`, `tests/fixtures/bls_lns14000000.json` (recorded).

- [ ] **Test (red) — windowing:** `year_windows(1948, 2026)` → `[(1948,1967),(1968,1987),(1988,2007),(2008,2026)]`; contiguous, ≤20yr, none before start. Hypothesis: for any `start≤end`, windows cover `[start,end]`, each span ≤20, monotonic.
- [ ] **Test (red) — parse:** given recorded JSON fixture, `fetch_series([spec], config, fake_http)` returns long DataFrame with columns `series_id,year,period,date,value,footnotes`; `value` float; `date` = period-end Timestamp; `M13`/annual flagged.
- [ ] **Test (red) — batching/budget:** a `FakeHttpPoster` records calls; 120 specs → batched ≤50/call; budget=2 stops after 2 calls and report flags `budget_exceeded`.
- [ ] **Test (red) — error surfacing:** fixture with `status:"REQUEST_NOT_PROCESSED"`/"Series does not exist" → no crash, series listed in `report.failed`.
- [ ] Run → fail.
- [ ] **Green:** `HttpPoster` Protocol (`post(url, payload) -> dict`); `year_windows`; `fetch_series` orchestrates batches×windows over injected http, parses, dedupes, builds `FetchReport`. Real `RequestsHttpPoster` with retry/backoff (used only in CLI/integration).
- [ ] Run → pass. Commit `feat: BLS API client with windowing+budget`.

---

### Task 4: cache.py — delta + revision-aware merge

**Files:** Create `cache.py`, `tests/test_cache.py`.

- [ ] **Test (red):** `ParquetCache(tmp_path).missing_ranges(specs)` returns full range when empty; after writing obs through 2025-10, returns `2025-? → now` PLUS trailing `revision_refetch_months`. `merge(old, new)` dedupes `(series_id,date)` keeping newest fetch; sets `latest_flag` on max date per series. Hypothesis: any two overlapping frames merge with no dup keys.
- [ ] Run → fail. **Green:** implement load/merge/write parquet; revision window; latest_flag. Run → pass. Commit `feat: revision-aware parquet cache`.

---

### Task 5: crosswalks.py + exposure.py — joins

**Files:** Create `crosswalks.py`, `exposure.py`, `tests/test_exposure.py`, mini fixtures (`tests/fixtures/aioe_mini.xlsx`, `gpts_mini.csv`, `census_soc_mini.xlsx`).

- [ ] **Test (red):** `onet_to_soc6("15-1252.00")=="151252"`. `load_gpts(mini_csv)` collapses O*NET-SOC→SOC6 with mean of `beta`. `load_aioe(mini_xlsx)` returns `soc6,aioe,aioe_langmod`. `build_exposure_occupation()` join completeness: given AI_SOC list, ≥ threshold matched; unmatched returned.
- [ ] Run → fail. **Green:** implement loaders (download-with-cache stubbed via injected fetcher so tests use local fixtures), collapse, join. Real downloads from raw.githubusercontent.com / census.gov in a separate `fetch_reference()` used by CLI; graceful "manual download" message on failure. Run → pass. Commit `feat: crosswalks + AI-exposure join`.

---

### Task 6: datasets.py — output contract

**Files:** Create `datasets.py`, `tests/test_datasets.py`.

- [ ] **Test (red):** `write_datasets(obs, specs, exposure, out_dir)` writes `observations.parquet`, `series_meta.parquet`, `exposure_occupation.parquet`, `exposure_industry.parquet`; re-reading yields identical sorted frames (determinism); `series_meta` has one row per spec with all tag columns.
- [ ] Run → fail. **Green:** implement assembly + sorted parquet writes. Run → pass. Commit `feat: tidy dataset output contract`.

---

### Task 7: quality.py — validation gate

**Files:** Create `quality.py`, `tests/test_quality.py`.

- [ ] **Test (red):** coverage flags missing series; `REQUIRED_CORE` missing → `report.passed is False`. JOLTS identity `TS≈QU+LD+OS` violation detected (inject bad row). `U-3 == LNS14000000` check. Freshness staleness warns. `to_markdown()`/`to_json()` produce report strings.
- [ ] Run → fail. **Green:** implement checks + `QualityReport` dataclass + writers. Run → pass. Commit `feat: data-quality gate`.

---

### Task 8: CLI + public API wiring

**Files:** Create `cli.py`, `__main__.py`, fill `__init__.py`.

- [ ] **Test (red):** `fetch_all(config, http=fake)` runs registry→client→cache→exposure→datasets→quality end-to-end on fakes, returns `QualityReport`; `load_dataset("observations")` reads parquet.
- [ ] Run → fail. **Green:** wire `fetch_all`; argparse `fetch`/`quality`; key from env `BLS_API_KEY` (error if unset, never logged). Run → pass. Commit `feat: fetch_all orchestration + CLI`.

---

### Task 9: LIVE FETCH (verification, not unit test)

- [ ] `fetch_reference()` downloads AIOE/GPTs/Census crosswalk to `data/reference/` (fallback: skip exposure with a logged warning if a host blocks).
- [ ] Run `python -m unemployment_pipeline fetch` with real key (from `.env`). Respects 450/day budget; writes parquet + `quality/quality_report.md`.
- [ ] Verify: `observations.parquet` non-empty; `LNS14000000` history reaches 1948; quality report passes core checks. Log row/series counts.
- [ ] Commit data-free (`.gitignore` excludes `data/`): `chore: first live pull verified`.

---

### Task 10: Dashboard — light interactive HTML (impeccable UI)

**Files:** Create `dashboard/prepare.py`, `dashboard/charts.py`, `dashboard/build.py`, `tests/test_dashboard_prepare.py`. Output `output/dashboard.html`.

- [ ] **Test (red) — prepare:** pure functions over the parquet contract: `education_gradient(obs,meta)` returns tidy frame with the 4 education series + a `bachelor_minus_hs_gap` column; `ai_sector_index(obs)` rebases Information/PBS/total-nonfarm employment to 100 at Nov-2022; `tightness_ratio(obs)` = unemployment ÷ openings; `jolts_hires_openings(obs)` frame. Assert shapes/columns/known values on a small synthetic obs frame.
- [ ] Run → fail. **Green:** implement prepare functions. Run → pass.
- [ ] **charts.py:** Plotly figure builders (light template `plotly_white`): national KPI header, unemployment-rate time series with Nov-2022 marker, **education-gradient** lines + gap area, **AI-exposed sector employment index** (rebased), **JOLTS openings vs hires** in Information/PBS, **state choropleth** (latest UR by state), **labor-market tightness** ratio, **occupation × AI-exposure** scatter (employment change vs GPTs/AIOE score). Each returns a `go.Figure`.
- [ ] **build.py + impeccable:** assemble into ONE self-contained light HTML — apply the `impeccable` skill for layout, type scale, spacing, color, accessibility. Sticky section nav, KPI cards, responsive grid, clear titles/annotations, source footnotes, "correlation≠causation" caveat banner. Plotly via CDN-or-inline (self-contained). Write `output/dashboard.html`.
- [ ] Verify: open the HTML, confirm charts render and the AI-impact narrative reads (education gap, sector divergence, hiring slowdown). Screenshot/preview.
- [ ] Commit: `feat: AI-impact unemployment dashboard (light HTML)`.

---

## Self-Review

**Spec coverage:** config(T1)·registry/enumerators(T2)·client+windowing+budget(T3)·cache+revision(T4)·crosswalks/exposure(T5)·datasets contract(T6)·quality gate(T7)·CLI+key-from-env(T8)·live max-history fetch(T9). Dashboard (beyond Phase-1 spec, per user goal) = T10. ✓
**Placeholders:** none — each task has concrete test intent + signatures; full code authored at execution under TDD.
**Type consistency:** `SeriesSpec`/`FetchConfig` (T1) reused everywhere; `fetch_series`/`HttpPoster` (T3) consumed by T8; parquet contract (T6) consumed by T10 prepare. Names aligned.
**Note:** mypy/black optional (not installed); full type hints written regardless; pytest+hypothesis is the gate.

**Execution choice (auto, per goal "don't pause to ask"):** inline TDD in this session (interdependent pipeline → controllable, end-to-end verifiable), dispatching subagents only for isolated work (impeccable UI research). Using superpowers:test-driven-development per task.
