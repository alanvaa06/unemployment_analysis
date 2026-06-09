# Has AI taken a toll on US jobs?

An interactive, reproducible analysis of the US labor market built entirely on **Bureau of Labor
Statistics** data, instrumented to ask one question: **since ChatGPT launched (Nov 2022), is there a
detectable AI signal in employment, hiring, and unemployment?**

It pulls ~900 BLS series across five programs, caches them locally, joins external AI-exposure
indices, and renders a single self-contained HTML report whose decompositions, distributions, and
relationships **recompute in the browser** as you change the comparison dates.

> **Read with care.** Every exhibit shows correlation and timing, not causation. The 2022–2023
> window also contains the post-pandemic tech-hiring unwind and the Fed's rate-hike cycle. The
> report is deliberately built to argue against itself (a magnitude check, a baseline-flip control,
> an education counter-example).

---

## What's inside

**Data pipeline** (`unemployment_pipeline/`) — a declarative, tagged series registry feeding a
generic BLS API v2 client (full-history 20-year windowing, ≤50-series batching, daily-budget aware),
a revision-aware parquet cache, an AI-exposure join (AIOE/AIIE + GPTs-are-GPTs), and a data-quality
gate. ~960 series requested, ~930 returned, back to 1948 for the headline rate.

**Dashboard** (`dashboard/`) — a light, editorial, single-file HTML report (Plotly) with **13
exhibits** that go well beyond simple time series:

| Exhibit | Type | What it shows |
|---|---|---|
| Where the jobs went | contribution **waterfall** | net job change decomposed by industry (sums to the total) |
| Distribution of industry change | **beeswarm** (~180 industries) | the full shape of change, colored by AI exposure |
| How the distribution shifted | **histogram** | AI-exposed industries' 12-month changes vs the rest |
| Does exposure predict job loss? | **scatter + live OLS** | the thesis on trial, with an honest (weak) R² |
| Information vs a control | **event study** | indexed to the ChatGPT anchor, pre-trend visible |
| Hiring freeze or active cuts? | **JOLTS quadrant** | openings change vs layoffs change by industry |
| A decade of change + breadth | **heatmap + diffusion** | YoY by industry and the share of industries growing |
| State dispersion | **percentile fan** | how unevenly slack spreads across states |
| Every state by ΔUR + tech share | **beeswarm** (52 states) | the geographic incidence |
| The education shield | **gap area** | high-school-minus-bachelor's unemployment gap |
| Beveridge curve | connected scatter | the labor market's round trip to balance |
| The stakes | occupation bubble | where exposed workers sit (2025 snapshot) |

Charts that depend on a comparison window recompute client-side from a **baseline ↔ compare** date
selector (presets: 2019, ChatGPT, GPT-4).

**Local app** (`app.py`) — a small Flask server that serves the dashboard and adds:
- **Refresh from BLS** — re-fetch the latest data (warns if the cache was refreshed recently, since
  these series update monthly), with a loading overlay.
- **API-key box** — enter a BLS key at runtime; otherwise it uses `BLS_API_KEY` from `.env`.
- **Save as PDF** — print-to-PDF with a clean print stylesheet.
- **Export data (Excel)** — one sheet per chart of the underlying numbers.

---

## Quick start

```bash
pip install -r requirements.txt          # pandas, pyarrow, requests, plotly, flask, openpyxl, python-dotenv

# 1) get a free BLS API key: https://data.bls.gov/registrationEngine/  (emailed instantly)
echo "BLS_API_KEY=your_key_here" > .env   # .env is gitignored

# 2) fetch the data (first pull ~1-2 min; re-runs are incremental and cheap)
python -m unemployment_pipeline fetch

# 3) build the dashboard
python -m dashboard.interactive_build      # writes output/dashboard.html

# 4) run the app (enables Refresh / PDF / Excel buttons)
python app.py                              # http://127.0.0.1:8765
```

No key? The pipeline still runs on the public (keyless) tier with tighter limits; the dashboard also
opens as a static file (`output/dashboard.html`), though the Refresh/Export buttons need the app.

The curated, live-verified series universe ships in `data/reference/expanded_series.json` so you get
the full detailed-industry coverage without re-running enumeration.

---

## Key findings (verified from the data)

- **Information employment peaked the exact month ChatGPT launched** (Nov 2022): −332k jobs / −10.7%
  since, yet only −3.7% below 2019, so most of the decline is post-ChatGPT.
- **Computer systems design peaked the exact GPT-4 month** (Mar 2023).
- **The verdict flips with the baseline** — software publishers are +35% from 2019 but flat from
  2022. The date control makes that fragility explorable.
- **Information openings −61% with layoffs +43%** — active cutting, not a quiet freeze.
- **AI-exposed industries' 12-month changes sit a full distribution to the left** of the rest.
- **The education premium narrowed**, but graduates still hold the lower unemployment rate.

These are correlations with a striking timing coincidence, not identified causal effects.

---

## Data sources

- **BLS** — CPS (LN), LAUS (LA), CES/SAE (CE/SM), JOLTS (JT), OEWS (OE). See
  `docs/data/bls_series_catalog.md` for the verified series catalog.
- **AI exposure** — Eloundou, Manning, Mishkin & Rock (2023), *GPTs are GPTs*; Felten, Raj & Seamans,
  *AI Occupational / Industry Exposure (AIOE/AIIE)*.

## Development

```bash
python -m pytest -q        # 62 tests (TDD: pipeline, cache, analytics, exports)
```

Architecture and design notes live in `docs/superpowers/specs/`. Built test-first; the pipeline and
analytics are pure, deterministic functions with parquet IO at the edges.

## License & disclaimer

Public BLS data. This is exploratory economic analysis, not investment, policy, or causal advice.
Correlation ≠ causation; confounders (pandemic normalization, monetary policy) are real and called
out throughout.
