"""Pre-trend / placebo test for the Information-vs-control event study.

The estimator fits gap = log(emp_Information) - log(emp_control_ex_info) on a
clean pre-COVID window (2015-2019), projects it forward with a 95% PREDICTION
interval (HAC parameter variance + residual variance), and reports where the
observed gap leaves the band. No causal claim is asserted by the estimator.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from dashboard import advanced


def _synthetic_obs(gap_func, *, info_base=2800.0, control_level=120000.0,
                   start="2015-01", end="2026-05",
                   info_id="CES5000000001", tp_id="CES0500000001"):
    """Build a long obs frame for two series so that
    log(info) - log(total_private - info) == gap_func(decimal_year).

    control_level is the ex-Info control (total_private - info); total_private is
    reconstructed as control_level + info so the estimator's own subtraction
    (tp - info) recovers it.
    """
    dates = pd.date_range(start + "-01", end + "-01", freq="MS") + pd.offsets.MonthEnd(0)
    rows = []
    for d in dates:
        yr = d.year + (d.month - 1) / 12.0
        # deterministic seasonal wiggle -> nonzero residual variance (realistic
        # band width); period 12mo so it does not bias the annual slope.
        wiggle = 0.003 * np.sin(2 * np.pi * d.month / 12.0)
        gap = gap_func(yr) + wiggle
        info = control_level * np.exp(gap)        # so log(info)-log(control)=gap
        tp = control_level + info                  # total private = ex-info + info
        rows.append((info_id, d, info))
        rows.append((tp_id, d, tp))
    df = pd.DataFrame(rows, columns=["series_id", "date", "value"])
    return df


def test_recovers_known_pretrend_slope():
    # gap rises 2.0% per year in the pre-window (log-points ~ proportional)
    k = 0.02
    g = lambda yr: 0.10 + k * (yr - 2015.0)
    obs = _synthetic_obs(g)
    r = advanced.event_pretrend(obs)
    assert r["slope_pct_yr"] == pytest_approx(2.0, abs=0.05)
    lo, hi = r["slope_ci"]
    assert lo <= 2.0 <= hi


def test_no_break_when_observed_stays_on_trend():
    # same linear gap for the WHOLE sample -> observed never leaves the band
    g = lambda yr: 0.05 - 0.01 * (yr - 2015.0)
    obs = _synthetic_obs(g)
    r = advanced.event_pretrend(obs)
    assert r["exit_month"] is None


def test_detects_break_below_band_after_anchor():
    # follow trend until the anchor, then drop the gap sharply (Information
    # underperforms) -> observed leaves the band below, at the drop month.
    anchor = pd.Timestamp("2022-11-30")
    drop_start = pd.Timestamp("2023-06-30")

    def g(yr):
        base = 0.05 - 0.01 * (yr - 2015.0)
        # decimal year of drop_start ~ 2023 + 5/12
        return base - (0.20 if yr >= 2023 + 5 / 12 - 1e-9 else 0.0)

    obs = _synthetic_obs(g)
    r = advanced.event_pretrend(obs)
    assert r["exit_month"] is not None
    # exit at or right after the engineered drop
    assert pd.Timestamp(r["exit_month"]) >= anchor
    assert abs((pd.Timestamp(r["exit_month"]) - drop_start).days) <= 40


def test_covid_window_excluded_from_fit():
    # inject absurd 2020-2021 values; slope must be unchanged because those
    # months are excluded from the regression.
    k = 0.015
    base = lambda yr: 0.0 + k * (yr - 2015.0)

    def g(yr):
        if 2020.0 <= yr < 2022.0:
            return base(yr) + 5.0  # COVID nonsense, must NOT enter the fit
        return base(yr)

    obs = _synthetic_obs(g)
    r = advanced.event_pretrend(obs)
    assert r["slope_pct_yr"] == pytest_approx(1.5, abs=0.05)
    assert r["n_pre"] == 60  # 2015-01..2019-12 inclusive


def test_frame_has_index_space_counterfactual_columns():
    g = lambda yr: 0.05 - 0.01 * (yr - 2015.0)
    obs = _synthetic_obs(g)
    r = advanced.event_pretrend(obs)
    f = r["frame"]
    for col in ["date", "gap_obs", "fit", "pi_lo", "pi_hi",
                "treated_idx", "control_idx", "cf_idx", "cf_lo", "cf_hi"]:
        assert col in f.columns
    # at the anchor the indexed series are ~100 by construction
    a = f[f["date"] == r["anchor"]].iloc[0]
    assert a["treated_idx"] == pytest_approx(100.0, abs=1e-6)
    assert a["control_idx"] == pytest_approx(100.0, abs=1e-6)


# tiny local approx helper to avoid importing pytest.approx at module top
def pytest_approx(value, abs=1e-6):
    import pytest
    return pytest.approx(value, abs=abs)
