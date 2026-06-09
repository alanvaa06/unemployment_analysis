# Momentum Strategy — Spec v2

**Status:** design approved 2026-05-13. Supersedes v1 (cross-sectional top-decile on S&P 500 subset). v1 implementation in `momentum_backtest.py` retained as historical reference; new code lives under the `momentum_strategy/` package described below.

---

## 1. Goal

A multi-asset rotation strategy over a flexible user-supplied universe (stocks + ETFs together). Long-horizon momentum bias. Daily-runnable, low turnover via rank hysteresis. Each run produces a deterministic dictionary describing today's intended positions and full backtest stats through today — consumed by a downstream Claude routine that diffs vs the prior day and emits a webhook on change.

## 2. Scope

**In scope:**
- Single Python package (`momentum_strategy/`), pure Python, no service layer.
- Daily strategy evaluation on a user-supplied universe.
- Walk-forward backtest, ≥10y history, transaction-cost-aware.
- Deterministic output dictionary (+ JSON file + equity-curve CSV + rotation log).
- yfinance primary data source, Tiingo fallback.

**Out of scope:**
- Email composition / webhook delivery (separate Claude routine).
- Live trading execution, broker integration.
- Intraday signals.
- Shorts, leverage, options, derivatives.
- Defensive cash sleeve / regime filter (user-deferred — see §11).
- UI / dashboard.

## 3. Universe

User-supplied list. Stocks and ETFs treated identically by the engine (same adjusted-close pipeline, same signal math). Loaded from a `.txt` (one ticker per line) or passed as a Python list to `run_strategy()`.

Per-ticker history requirement: ≥ 252 trading days BEFORE the backtest start date (so the 12m lookback is valid at `start`). Tickers failing this are excluded with a logged warning and surfaced in `meta.dropped_short_history`.

Survivorship bias: present (user picks today's tickers). Not mitigated. Documented limitation.

## 4. Data Layer

### Module: `data.py`

```python
def fetch_prices(
    tickers: list[str],
    start: str,
    end: str | None,
    tiingo_key: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Returns (prices, meta) where:
      prices = DataFrame, index = trading days, columns = tickers, values = adj close.
      meta   = {
        "source_per_ticker":      {ticker: "yfinance" | "tiingo"},
        "missing_tickers":        [tickers entirely unfetchable],
        "dropped_short_history":  [tickers with < 252d history pre-start],
        "tiingo_fallback_used":   [tickers where yfinance failed and Tiingo succeeded],
      }
    """
```

### Provider routing per ticker

Order depends on whether `tiingo_key` is set. Tiingo-first when available because the strategy is designed to run inside cloud / Claude Code sandboxes where datacenter IPs hit Yahoo rate-limits (`YFRateLimitError`, empty frames, sporadic 429s). Avoiding the yfinance-fail-then-fallback round-trip saves latency.

**With `tiingo_key`:**
1. **Tiingo primary.** `GET https://api.tiingo.com/tiingo/daily/{ticker}/prices?startDate={start}` with `Authorization: Token {key}` header. Returns split- and dividend-adjusted close (field `adjClose`).
2. **yfinance fallback.** If Tiingo returns empty or HTTP error, try `yf.download(ticker, start, end, auto_adjust=True)`.

**Without `tiingo_key`:**
1. **yfinance only.** Same call as above. May fail in cloud sandboxes — documented limitation, not a bug.

**Accept rule (both paths):** series must have ≥ `MIN_HISTORY_DAYS` (252) bars after the configured `start`. Otherwise the ticker is dropped to `dropped_short_history`. If both providers return empty, the ticker is dropped to `missing_tickers`.

### Caching

`data_cache.parquet` next to script. Per-ticker delta-aware:

- Load cache. For each requested ticker, identify the missing date range (cache_max_date+1 → today).
- Fetch only the delta per ticker via the routing above.
- Concat new bars to cached series, deduplicate by date, sort, rewrite parquet.
- Stale-cache invalidation: if cache_max_date < (today − 5 business days), rewrite the full window for that ticker (handles split/div adjustment drift in yfinance).

Parallelization via `ThreadPoolExecutor` (max_workers = 8). Tiingo free tier = 500 req/h — sufficient for typical universes ≤ 100 names with delta fetches.

## 5. Signal

### Module: `signal.py`

```python
def blended_momentum_score(
    prices: pd.DataFrame,
    asof: pd.Timestamp,
    w_3m: float = 0.3,
    w_12m: float = 0.7,
    skip_days: int = 21,
    lookback_3m_days: int = 63,
    lookback_12m_days: int = 252,
) -> pd.Series:
    """Blended momentum score per ticker at asof. NaN where history insufficient."""
    p_skip = prices.shift(skip_days).loc[asof]
    p_3m   = prices.shift(skip_days + lookback_3m_days).loc[asof]
    p_12m  = prices.shift(skip_days + lookback_12m_days).loc[asof]
    r_3m  = p_skip / p_3m  - 1
    r_12m = p_skip / p_12m - 1
    return w_3m * r_3m + w_12m * r_12m
```

**Design notes.**
- Trading-day shifts, not calendar. Robust to holidays and yfinance index quirks.
- Skip applied once at the recent end; each lookback measured from `p_skip`. Reads as: "return from t-12m to t-21d, blended with return from t-3m to t-21d."
- Weights are kwargs. Override per backtest without touching call sites.
- NaN-tolerant — downstream ranking drops NaNs before applying hysteresis.

## 6. Portfolio Construction

### Module: `portfolio.py`

Pure functions. No hidden state between calls — prior state is an explicit input.

```python
@dataclass(frozen=True)
class HysteresisConfig:
    n_in: int    # rank cutoff to ENTER (e.g., 5 → must rank top 5 to enter)
    n_out: int   # rank cutoff to KICK OUT (e.g., 10 → only kicked when rank > 10)
    # Validated: n_out >= n_in, both >= 1.

def update_holdings(
    prior_holdings: set[str],
    scores: pd.Series,         # today's scores; NaNs already dropped
    cfg: HysteresisConfig,
) -> list[str]:
    """
    Returns ordered list of today's held tickers (by rank).

    Rules:
      1. ranks = scores.sort_values(ascending=False); rank 1 = best.
      2. KEEP set: tickers in prior_holdings with rank <= n_out.
      3. ADD candidates: tickers NOT in prior_holdings with rank <= n_in.
      4. Held = KEEP + ADDs, capped at n_in total, filled by rank order.
      5. Tickers in prior_holdings but missing from scores are forced exits.
    """

def size_positions(held: list[str], scores: pd.Series) -> dict[str, float]:
    """
    Score-weighted with safety rails:
      1. pos_scores = scores[held].clip(lower=0)
      2. If pos_scores.sum() == 0: return {t: 1/len(held) for t in held}  # equal-weight fallback
      3. Else: return (pos_scores / pos_scores.sum()).to_dict()
    """
```

**Edge cases.**
- Empty `prior_holdings` on day 0 → all entrants drawn from top `n_in` ranks.
- Fewer than `n_in` valid (non-NaN) scores → hold what's available, no padding.
- Ticker drops out of `scores` mid-run (data gap, delisting) → forced exit, weights redistributed next bar.
- `n_out == n_in` is legal but degenerates to "rotate every day if any rank slips." `HysteresisConfig.__post_init__` emits a `warnings.warn(...)` when this case is detected.
- `n_out < n_in` or any value `< 1` raises `ValueError` in `HysteresisConfig.__post_init__`.

## 7. Backtest Engine

### Module: `backtest.py`

```python
@dataclass(frozen=True)
class BacktestConfig:
    n_in: int
    n_out: int
    w_3m: float = 0.3
    w_12m: float = 0.7
    skip_days: int = 21
    tc_bps: float = 5.0          # per side; round-trip = 2 * tc_bps
    start: str = "2014-01-01"    # ≥ 10y default

@dataclass
class BacktestResult:
    equity: pd.Series                       # daily equity curve, starts at 1.0
    weights_history: pd.DataFrame           # index = date, cols = ticker, values = weight
    rotation_log: list[dict]                # one entry per weight-change day
    stats: dict                             # see §9
```

**Walk-forward loop (daily).** Warmup = `skip_days + lookback_12m_days` = 273 trading days. From the first valid date:

```
prior_holdings = set()
prior_weights = {}
equity = 1.0
for t in trading_days[start_idx:]:
    scores_t = blended_momentum_score(prices, t, ...).dropna()
    held_t = update_holdings(prior_holdings, scores_t, cfg)
    weights_t = size_positions(held_t, scores_t)
    if weights_t != prior_weights:
        turnover = sum(|w_new - w_old|) / 2 (over union of tickers)
        equity *= 1 - 2 * turnover * (tc_bps / 1e4)
        log rotation event {date: t, in: [...], out: [...], turnover: float}
    # next-bar return realized t → t+1
    if t+1 exists:
        port_ret = sum(weights_t[k] * (prices.loc[t+1, k] / prices.loc[t, k] - 1))
        equity_at_t+1 = equity * (1 + port_ret)
    prior_holdings = set(held_t)
    prior_weights  = weights_t
```

**No look-ahead.** Signal computed on close of `t`, position established at close of `t`, return earned `t → t+1`. TC charged on `t` (the day weights change).

## 8. Output Layer

### Module: `output.py`

```python
def build_run_dict(
    prices_meta: dict,
    today: pd.Timestamp,
    universe: list[str],
    scores: pd.Series,
    weights: dict[str, float],
    bt: BacktestResult,
    cfg: BacktestConfig,
) -> dict:
    """Assembles the canonical run dictionary (schema v1)."""
```

### Run dictionary schema (v1)

```python
{
    "as_of":           "2026-05-13",                  # ISO date, last bar used
    "schema_version":  1,
    "universe":        ["AAPL", "MSFT", "SPY", ...],  # post data-quality filter

    "positions": {                                    # today's intended holdings
        "AAPL": 0.4231,
        "MSFT": 0.3104,
        "NVDA": 0.2665,
    },                                                # sum = 1.0 (or 0.0 if no qualifiers)

    "scores": {                                       # blended score for every universe name
        "AAPL":  0.234,
        "MSFT":  0.198,
        "TLT":  -0.087,
    },
    "ranks": {                                        # rank 1 = best; NaN-score tickers omitted
        "AAPL": 1, "MSFT": 2, "NVDA": 3,
    },

    "stats": {                                        # full-history backtest stats through as_of
        "cagr":          0.142,
        "vol":           0.180,
        "sharpe":        0.789,
        "sortino":       1.034,
        "max_dd":       -0.241,
        "calmar":        0.589,
        "hit_rate":      0.551,
        "turnover_avg":  0.124,
        "n_rotations":   18,
        "avg_hold_days": 87,
        "time_in_cash":  0.0,
        "n_bars":        2823,
    },

    "config": {                                       # snapshot — diff routine flags param drift
        "n_in":      5,
        "n_out":     10,
        "w_3m":      0.3,
        "w_12m":     0.7,
        "skip_days": 21,
        "tc_bps":    5.0,
        "start":     "2014-01-01",
        "signal":    "blended_3m_12m_skip_1m",
    },

    "meta": {
        "run_timestamp_utc":      "2026-05-13T22:15:00Z",
        "data_source_per_ticker": {"AAPL": "yfinance", "TSM": "tiingo"},
        "missing_tickers":        [],
        "dropped_short_history":  ["NEWIPO"],
        "tiingo_fallback_used":   ["TSM"],
    },
}
```

**Determinism.** Same universe + same `as_of` + same config = identical dict byte-for-byte EXCEPT `meta.run_timestamp_utc`. Lets the downstream diff routine compare with `==` after popping that one field.

### Persistence

`run_strategy()` returns the dict AND writes:

- `output/run_<as_of>.json` — pretty-printed JSON of the dict.
- `output/equity_curve.csv` — full daily equity Series (overwritten each run).
- `output/rotation_log.csv` — append-only history of all rotation events (date, in, out, turnover).

Downstream diff routine reads `output/run_<yesterday>.json` vs `output/run_<today>.json`.

## 9. Stats Definitions

| Stat | Formula |
|------|---------|
| CAGR | `(equity[-1] / equity[0]) ** (252 / n_bars) - 1` |
| Vol | `equity.pct_change().std() * sqrt(252)` |
| Sharpe | `(CAGR - rf) / Vol`, `rf = 0` |
| Sortino | `(CAGR - rf) / (downside_vol)`, downside = std of negative daily returns × √252 |
| MaxDD | `min(equity / equity.cummax() - 1)` |
| Calmar | `CAGR / |MaxDD|` |
| HitRate | `(daily_returns > 0).mean()` |
| Turnover_avg | mean of per-rotation `sum(|w_new - w_old|) / 2` |
| N_rotations | count of days `weights_t != prior_weights` |
| Avg_hold_days | mean position life across all closed positions in `rotation_log` |
| Time_in_cash | fraction of bars with `sum(weights) < 1` (≈ 0 by design) |

## 10. Public API + CLI

### Public

```python
from momentum_strategy import run_strategy

result = run_strategy(
    universe=["AAPL", "MSFT", "SPY", "QQQ", "TLT", "GLD"],
    start="2014-01-01",
    n_in=5, n_out=10,
    w_3m=0.3, w_12m=0.7,
    tc_bps=5,
    tiingo_key=None,
    output_dir="output",
)
# result is the run dictionary; files also written to output_dir.
```

### CLI

```
python -m momentum_strategy.cli \
    --universe-file universe.txt \
    --start 2014-01-01 \
    --n-in <int> --n-out <int> \
    [--w-3m 0.3] [--w-12m 0.7] \
    [--tc-bps 5] \
    [--output-dir output] \
    [--tiingo-key $TIINGO_KEY]
```

**Required:** `--universe-file`, `--n-in`, `--n-out` (no defaults — user chose configurable per spec §6).
**Defaults applied when omitted:** `--start=2014-01-01`, `--w-3m=0.3`, `--w-12m=0.7`, `--tc-bps=5`, `--output-dir=output`.

`universe.txt`: one ticker per line, `#`-prefixed comments allowed. The daily Claude routine swaps lists by editing this file — no code change needed.

## 11. Limitations

- **No defensive overlay.** Pure relative momentum. Always invested. Expect 2008/2020/2022-style drawdowns proportional to the universe trend.
- **Survivorship bias.** User-supplied universe = today's universe. No point-in-time membership.
- **yfinance / Tiingo adjusted close.** Total-return proxy (divs reinvested). Borrow, slippage, market impact ignored.
- **TC model.** Flat bps charged on weight-change days. Doesn't model bid-ask, partial fills, after-hours moves.
- **Score-weighted concentration.** With small universes + one dominant winner, single-name weight can exceed 50%. No per-name cap baked in — easy add later (config field) if needed.
- **Idempotency.** Multiple intra-day runs on the same `as_of` produce identical dicts (only `meta.run_timestamp_utc` differs). Latest run's JSON overwrites prior on the same date.

## 12. File Layout

```
momentum_strategy/
├── __init__.py           # public API: run_strategy(...)
├── data.py               # fetch + cache; yfinance + Tiingo fallback
├── signal.py             # blended_momentum_score
├── portfolio.py          # HysteresisConfig, update_holdings, size_positions
├── backtest.py           # BacktestConfig, BacktestResult, run_backtest
├── output.py             # build_run_dict + file writers
└── cli.py                # argparse entry; calls run_strategy
tests/
├── test_data.py
├── test_signal.py
├── test_portfolio.py     # truth-table tests + Hypothesis property tests
├── test_backtest.py
└── test_output.py
output/                   # created at first run
├── run_<as_of>.json
├── equity_curve.csv
├── rotation_log.csv
└── data_cache.parquet
docs/prd/PRD.md           # this file
momentum_backtest.py      # v1 legacy script, retained as historical reference
```

## 13. Testing

Pytest, per `docs/references/python_best_practices.md`. Arrange-Act-Assert, fixtures, full type hints, dataclasses for configs.

**Coverage targets:**
- `test_signal.py` — known-input synthetic price frames, hand-computed expected scores. NaN propagation. Skip-days correctness: build a series with a huge day-(-1) spike, confirm the skip excludes it.
- `test_portfolio.py` — hysteresis truth table. Example: `prior={A,B,C}`, ranks `{A:1, B:8, C:11, D:2, E:4}`, `n_in=3, n_out=10` → keep A + B, drop C, add D (fills opened slot). Sizing edge cases: all-negative scores → equal-weight; mixed → clipped-and-renormalized.
- `test_backtest.py` — synthetic 3-ticker world with deterministic trends. Verify CAGR, n_rotations, TC accounting. No-trade case: weights unchanged → equity step has zero TC. Forced-exit on NaN.
- `test_output.py` — `schema_version` stamped; missing tickers surface in `meta`; positions sum to 1.0 (or 0.0). Round-trip JSON dump/load is bit-identical.

Property-based via Hypothesis for `update_holdings`: any ranks, any prior set → invariants `held ⊆ ranked`, `|held| ≤ n_in`, no held has rank > n_out, no entrant has rank > n_in.

## 14. Acceptance Criteria

- [ ] `pip install yfinance pandas numpy pyarrow requests pytest hypothesis` + `python -m momentum_strategy.cli --universe-file universe.txt` runs end-to-end on a 10-name mixed stock+ETF universe.
- [ ] Output dict matches schema v1 exactly; `output/run_<today>.json` written.
- [ ] Determinism check: two consecutive runs same minute produce identical dicts after popping `meta.run_timestamp_utc`.
- [ ] Test suite green: ≥ 4 module test files, ≥ 25 tests total, all passing.
- [ ] Backtest reproduces sensible stats on a known-good universe (e.g. [SPY, QQQ, EFA, EEM, TLT, GLD, DBC] from 2014): Sharpe > 0.4, MaxDD bounded, n_rotations < 30/year.
- [ ] Tiingo fallback verified end-to-end on a ticker yfinance handles poorly (e.g. a non-US ADR).
- [ ] No look-ahead: a test that injects future-only data and asserts it doesn't leak into a prior-date score.

## 15. Future Work (Out of v1 Scope)

- Per-name weight cap (config field).
- Optional defensive overlay (per-name absolute momentum filter and/or SPY-200d regime gate) — gated on a config flag.
- Volatility scaling on signal or position sizing.
- Multi-frequency rebalance (weekly / monthly cadence option alongside daily).
- Equity curve plot generation (matplotlib).
- Direct-to-webhook emission (currently downstream Claude routine handles delivery).

## §15 Reporting Layer (added 2026-05-14)

The reporting layer sits on top of `run_backtest` and produces institutional-grade backtest reports without modifying the engine. See `docs/superpowers/specs/2026-05-14-backtest-analytics-design.md` for the full design.

### Modules

- `momentum_strategy.analytics` — pure metric functions returning frozen dataclasses. No IO.
- `momentum_strategy.reporting` — plots + HTML rendering. All file IO.

### Public entry

`run_backtest_report(universe, start, end, n_in, n_out, tc_bps, benchmark, output_dir, ...)`
returns `{report_path, stats, ic_summary, benchmark_summary, output_dir}`.

### Analytics

- `ExtraRiskMetrics`: VaR 95, CVaR 95, skew, excess kurtosis, best/worst day, longest drawdown.
- `RollingMetrics`: 252d rolling Sharpe, vol, beta vs benchmark; drawdown series; monthly returns matrix.
- `BenchmarkComparison`: excess return, tracking error, IR, beta, alpha, correlation, up/down capture.
- `TurnoverAnalysis`: daily turnover series, rotation cadence, annualized turnover, TC drag in bps, top held tickers.
- `ICResult` × 9 (3 signals: mom_3m, mom_12m, blended; 3 horizons: 21, 63, 252 days). Spearman IC, IC IR, t-stat, hit rate, annualized quintile spread.

### Reporting outputs

`output/backtest_<as_of>/`:
- `report.html` (interactive equity via plotly + 12 embedded PNGs).
- `plots/01..12_*.png`.
- `stats.json`, `ic_table.csv`, `weights_matrix.csv`, `rotation_log.csv`, `monthly_returns.csv`.

### CLI

`python -m momentum_strategy backtest --universe-file ... --start ... --n-in ... --n-out ... --benchmark SPY`.
The CLI now uses subparsers: `live` (default, today's run dict) and `backtest`.
