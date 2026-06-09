# Advanced Visualization Suite — Design Spec

**Status:** design selected 2026-06-09 via a 5-lens design tournament (macro, AI-impact, data-journalism, distribution, interactivity). Replaces the simple-time-series exhibits with decomposition / difference / distribution / relationship / heatmap charts driven by the existing baseline↔compare control. Supersedes the prior exhibit set in `dashboard/interactive_build.py`.

**Goal:** A 9-chart (plus 1 caveat coda) interactive storytelling suite answering "has AI taken a toll on US jobs?" using powerful, non-trivial encodings, every "change" chart recomputed client-side from a user-chosen baseline and compare month.

## Cross-cutting decisions (correctness)
- **Clean industry partition.** Histograms/waterfall/distribution/diffusion use a fixed **non-overlapping leaf set** (~18-20 industries): mining&logging, construction, durable mfg, nondurable mfg, wholesale, retail, transport&warehousing, utilities, **Information sub-industries** (software publishers, data processing/web hosting, computer systems design, telecom, publishing, broadcasting, motion picture, web/other), financial activities, professional/scientific/technical (54), management (55), admin&waste (56), private education&health, leisure&hospitality, other services, government. Never mix an aggregate with its children. Encode this set explicitly; validate it sums to ~total private+gov within tolerance.
- **Small-N honesty.** ~20 industries → render distribution as a **labeled strip/dot plot** (optionally ≤8-bin histogram), never a fake fine-grained histogram. ~52 states → boxplot/fan, not KDE.
- **Beveridge is national only** (no industry-level unemployment exists): U-3 (`LNS14000000`) vs JOLTS openings rate (`JTS000000000000000JOR`), monthly 2000→.
- **OEWS = single 2025 snapshot** → cross-sectional "stakes" bubble only; never a trend claim.
- **Exposure joins:** industries → AIIE (`exposure_industry.parquet`, NAICS); occupations → GPTs beta/AIOE (SOC). Show fitted slope + R² and label correlational.
- **Standing caveat on every panel:** correlation ≠ causation; the 2022-23 window also holds the post-pandemic tech-hiring unwind and Fed rate hikes.

## Shared interactivity
One sticky control bar (already built): **Baseline ▸ B**, **Compare ▸ C** month selectors with preset chips (Dec-2019, Nov-2022 ChatGPT, Mar-2023 GPT-4, Latest). On change, JS recomputes every "change" chart via `Plotly.react` (mirrors `bundle.change_since`; build NEW arrays each call). Anchor lines (ChatGPT, GPT-4) drawn on time-axis charts. `prefers-reduced-motion` respected for the Beveridge animation.

## The suite (ordered for storytelling)

**1. Net job-change contribution waterfall — HOOK.** Horizontal waterfall; signed per-industry contribution to total nonfarm change B→C, ranked, summing to the net (with an "all other" reconciling bar). Clay=loss, slate=gain. *Interactive* (B,C; toggle jobs vs %). Rationale: net employment is an accounting identity; decomposition disciplines the narrative and shows AI-exposed sectors' true magnitude.

**2. Distribution of industry change — strip/dot.** One dot per leaf industry on a "% change B→C" axis; color = AIIE tercile; size = employment; AI-exposed labeled. *Interactive* (B,C). Rationale: shows whether the pain is concentrated in the left tail (AI-exposed) or broad. The user's "histogram of changes."

**3. Exposure → employment-change scatter (dose-response).** x = AIIE (industry); y = % change B→C; size = employment; OLS fit line + slope/R² readout. *Interactive* (B,C). Rationale: the reduced-form AI-employment relationship drawn; the slope is the thesis. Caveat: AIIE is potential not adoption; weak predictor.

**4. Event-study trend-break vs control.** Indexed lines (=100 at anchor): AI-exposed group (Information) vs control (total private ex-Information); shaded pre-anchor extrapolation band from a linear pre-trend fit; ChatGPT/GPT-4 rules. *Interactive* (anchor toggle; control dropdown). Rationale: the falsifiable identification chart — divergence only after the anchor supports the story; pre-trend divergence undercuts it.

**5. Hiring freeze vs active cuts — JOLTS quadrant.** Scatter per JOLTS industry: x = openings-rate change, y = layoffs-rate change, B→C; quadrant labels ("demand freeze" vs "active shakeout"); bubble = employment. *Interactive* (B,C). Rationale: distinguishes a hiring freeze (AI-at-the-margin) from outright firing; our data shows Information openings −61% with layoffs +43%.

**6. Industry × time heatmap + diffusion breadth.** Diverging heatmap (rows = leaf industries sorted by AIIE, cols = years, color = YoY %), with a top strip = employment diffusion index (% of industries growing, 50-line, ±4 band). Rationale: heatmap = where/when; diffusion = whether weakness is broad (macro) or concentrated (sectoral).

**7. Cross-state unemployment dispersion.** Percentile fan (p10/p25/p50/p75/p90 across 52 states) over time + companion labor-force-weighted std-dev line; SA, 3-month-avg. Rationale: AI is spatially concentrated; widening dispersion beyond its historical band is signal the national rate hides.

**8. Education gradient gap — counter-evidence.** Filled "gap" series: HS-minus-bachelor's UR over time, with pre/post-ChatGPT averages annotated; ChatGPT rule. Rationale: GenAI uniquely targets cognitive/degreed work, so a narrowing graduate advantage is the fingerprint; currently the gap narrowed (2.82→1.79pp) but grads weren't hit harder in levels — credibility/counter-evidence beat.

**9. National Beveridge curve — animated macro context.** Connected scatter path: x = U-3, y = JOLTS openings rate, monthly 2000→, colored by time, play/slider; 45° efficiency reference; ChatGPT/GPT-4 dots flagged. Rationale: the curve's loop/outward-shift diagnoses structural vs cyclical change; the market round-tripped overheated→balanced (V/U 1.80→0.87→1.03).

**10. (Coda) Occupation exposure-wage bubble — stakes, static.** x = GPTs beta, y = 2025 median wage, size = employment. Rationale: maps where exposed workers sit today; explicit "exposure ≠ observed displacement; n small; snapshot only."

## Files
- `dashboard/advanced.py` (NEW) — pure prepare functions: `LEAF_INDUSTRIES`, `industry_change_table`, `contribution_waterfall`, `industry_change_distribution`, `diffusion_index`, `state_ur_dispersion`, `beveridge_series`, `event_study_indexed`, `exposure_industry_change` (+ embeddable monthly bundle for the leaf set with `naics`/`aiie`).
- `dashboard/charts_advanced.py` (EXTEND) — `fig_waterfall`, `fig_change_strip`, `fig_exposure_scatter`, `fig_event_study`, `fig_freeze_cuts`, `fig_heatmap_diffusion`, `fig_dispersion_fan`, `fig_education_gap`, `fig_beveridge` (+ keep existing).
- `dashboard/interactive_build.py` (REWRITE exhibits) — embed leaf bundle + AIIE; JS recompute for charts 1,2,3,5; server-render 4,6,7,8,9,10; new nav + findings retained.
- `tests/test_advanced.py` (NEW) — TDD the pure functions.

## Testing (TDD)
Per `docs/references/python_best_practices.md`. Pure functions get red→green tests with synthetic frames: leaf partition has no parent/child overlap and is non-empty; `contribution_waterfall` contributions sum to the net (± reconciling); `industry_change_distribution` returns one row per leaf with AIIE tier; `diffusion_index` = share growing in [0,100]; `state_ur_dispersion` std-dev is LF-weighted; `beveridge_series` aligns U and V by month; `event_study_indexed` =100 at anchor and control present; `exposure_industry_change` joins AIIE and drops unmatched. Browser-verify interactivity (baseline change recomputes) + render (DOM has each chart's traces).

## Acceptance criteria
- [ ] 9 core charts + coda render in `output/dashboard.html`; full suite ≥9 Plotly graphs.
- [ ] Baseline/compare change live-recomputes charts 1,2,3,5 (verified via DOM diff in browser).
- [ ] Leaf partition validated non-overlapping; waterfall reconciles to net nonfarm change.
- [ ] Beveridge animates (frames = years); dispersion fan + std-dev render; event-study shows pre-trend band.
- [ ] All `test_advanced.py` green + existing suite stays green; no em dashes; standing caveat present.
- [ ] Economic rationale + correlation caveat shown on each panel.

---
*Selected from 5 proposals; full proposals captured in this session. Best single chart (consensus): the exposure→change scatter with live OLS (thesis on trial) and the event-study trend-break (falsifiable) as co-heroes; waterfall is the hook.*
