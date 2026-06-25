# TODO

## Phase 1 — Series gathering (DONE)
- [x] Locate BLS API key guidance
- [x] Catalog CPS / LAUS / CES / JOLTS / OEWS+EP series
- [x] Catalog AI-exposure mapping datasets + join strategy
- [x] Write master catalog → `docs/data/bls_series_catalog.md`

## Phase 2 — Pipeline build (DONE 2026-06-08)
- [x] BLS_API_KEY in .env (gitignored)
- [x] Spec + plan written
- [x] config + registry + programs/ enumerators (809 series)
- [x] bls_client (max-history windowing, batching, budget, retry)
- [x] cache (delta + revision-aware) + datasets output contract
- [x] crosswalks + exposure join (AIOE, GPTs-are-GPTs)
- [x] quality checks + report (PASS on live data)
- [x] TDD tests (44 passing, pytest + hypothesis)
- [x] Live fetch verified (785 series, 398k rows, 1948→2026)

## Phase 3 — Report/dashboard (DONE 2026-06-09)
- [x] Interactive HTML/Plotly dashboard `output/dashboard.html` (light, impeccable UI)
- [x] Descriptive AI-impact exhibits (education gradient, sector divergence, occupation exposure, pre/post Nov-2022)
- [x] Verified rendering in-browser
- [x] Expanded to 931 series; industry/JOLTS/education-distribution exhibits
- [x] INTERACTIVE: client-side baseline/compare date picker (recomputes live)
- [x] Creative viz: heatmap, boxplot, animated choropleth, demand scatter
- [x] "Six findings" lead section from insight-mining workflow (verified)
- [x] Advanced-viz suite (5-lens tournament -> spec -> TDD): waterfall, distribution, exposure scatter w/ OLS, event-study, freeze-vs-cuts, heatmap+diffusion, dispersion fan, education gap, Beveridge, occupation bubble; 4 client-side interactive; 59 tests green

## Phase 5 — Publish to GitHub Pages (DONE 2026-06-25)
- [x] `static=True` mode on `build_interactive` (drops server-only buttons, keeps PDF)
- [x] `dashboard/publish.py` → repo-root `index.html` + `.nojekyll`
- [x] Merge to main, enable Pages (main/root), verify live
- [x] Live: https://alanvaa06.github.io/unemployment_analysis/

## Phase 4 — Econometric layer (DEFERRED — next)
- [ ] Diff-in-diff / event study, continuous exposure × post-2022, parallel-trends
- [ ] Multiple exposure indices + outcome sources (CPS vs payroll)

## Backlog
- [ ] Rotate BLS API key (was pasted in chat)
- [ ] mypy strict + black/flake8 config (optional gate)
- [ ] Expand registry to full ~2,800 series; counties/cities; OEWS state/metro
