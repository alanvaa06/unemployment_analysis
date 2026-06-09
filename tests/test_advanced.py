"""Tests for advanced-viz prepare functions."""
from __future__ import annotations

import pandas as pd
import pytest

from dashboard.advanced import (
    LEAF_PARTITION,
    contribution_waterfall,
    diffusion_index,
    event_study_indexed,
    exposure_industry_change,
    state_ur_dispersion,
)


def _obs(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame({
        "series_id": [r[0] for r in rows],
        "date": [pd.Timestamp(r[1]) for r in rows],
        "value": [r[2] for r in rows],
    })


def _meta(rows: list[dict]) -> pd.DataFrame:
    cols = ["series_id", "program", "label", "geo_level", "measure", "seasonal", "industry_naics"]
    return pd.DataFrame([{c: r.get(c) for c in cols} for r in rows])


def test_leaf_partition_no_parent_child_overlap() -> None:
    codes = [sid[3:11] for sid, _, _ in LEAF_PARTITION]
    assert len(codes) == len(set(codes))           # unique
    # no industry code is a prefix-aggregate of another in the set (clean leaves)
    assert "00000000" not in codes and "05000000" not in codes  # no total nonfarm/private


def test_contribution_waterfall_sums_to_net() -> None:
    a, b, _ = LEAF_PARTITION[0]
    c, d, _ = LEAF_PARTITION[1]
    obs = _obs([
        (a, "2022-11-30", 100.0), (a, "2026-05-31", 121.0),   # +21
        (c, "2022-11-30", 200.0), (c, "2026-05-31", 180.0),   # -20
    ])
    meta = _meta([
        {"series_id": a, "program": "CES", "label": b, "geo_level": "national", "measure": "ces_01", "seasonal": "SA"},
        {"series_id": c, "program": "CES", "label": d, "geo_level": "national", "measure": "ces_01", "seasonal": "SA"},
    ])
    wf = contribution_waterfall(obs, meta, "2022-11", "2026-05")
    assert wf["contribution_k"].sum() == pytest.approx(1.0)   # +21 -20
    assert set(wf["label"]) == {b, d}


def test_diffusion_index_share_growing() -> None:
    a = LEAF_PARTITION[0][0]
    c = LEAF_PARTITION[1][0]
    obs = _obs([
        (a, "2026-04-30", 100.0), (a, "2026-05-31", 101.0),   # up
        (c, "2026-04-30", 100.0), (c, "2026-05-31", 99.0),    # down
    ])
    di = diffusion_index(obs, window_months=1)
    latest = di[di["date"] == di["date"].max()]["diffusion"].iloc[0]
    assert latest == pytest.approx(50.0)                      # 1 of 2 growing


def test_state_ur_dispersion_lf_weighted_std() -> None:
    obs = _obs([
        ("LASST060000000000003", "2026-05-31", 6.0), ("LASST060000000000006", "2026-05-31", 1000.0),
        ("LASST480000000000003", "2026-05-31", 4.0), ("LASST480000000000006", "2026-05-31", 1000.0),
    ])
    disp = state_ur_dispersion(obs)
    row = disp[disp["date"] == pd.Timestamp("2026-05-31")].iloc[0]
    assert row["p50"] == pytest.approx(5.0)
    # equal LF weights -> weighted std == population std of {6,4} = 1.0
    assert row["wstd"] == pytest.approx(1.0, abs=1e-6)


def test_event_study_indexed_is_100_at_anchor() -> None:
    treated = "CES5000000001"
    control = "CES0500000001"
    obs = _obs([
        (treated, "2022-11-30", 3000.0), (treated, "2023-11-30", 2700.0),
        (control, "2022-11-30", 130000.0), (control, "2023-11-30", 134000.0),
    ])
    es = event_study_indexed(obs, anchor="2022-11", treated_id=treated, control_ids=[control])
    at = es[es["date"] == pd.Timestamp("2022-11-30")].iloc[0]
    assert at["treated"] == pytest.approx(100.0)
    assert at["control"] == pytest.approx(100.0)
    later = es[es["date"] == pd.Timestamp("2023-11-30")].iloc[0]
    assert later["treated"] == pytest.approx(90.0)


def test_state_ur_change_techshare() -> None:
    from dashboard.advanced import state_ur_change_techshare
    obs = _obs([
        ("LASST060000000000003", "2022-11-30", 4.0), ("LASST060000000000003", "2026-05-31", 5.5),
        ("SMS06000000000000001", "2026-05-31", 18000.0),   # CA total nonfarm
        ("SMS06000005000000001", "2026-05-31", 540.0),     # CA Information
        ("SMS06000006000000001", "2026-05-31", 2700.0),    # CA PBS
        ("LASST480000000000003", "2022-11-30", 4.0), ("LASST480000000000003", "2026-05-31", 4.2),
    ])
    out = state_ur_change_techshare(obs, "2022-11", "2026-05")
    ca = out[out["abbr"] == "CA"].iloc[0]
    assert ca["d_ur"] == pytest.approx(1.5)              # 5.5 - 4.0 pp
    assert ca["tech_share"] == pytest.approx((540 + 2700) / 18000 * 100)  # 18.0%
    # TX has no SM series -> tech_share NaN but row still present with d_ur
    tx = out[out["abbr"] == "TX"].iloc[0]
    assert tx["d_ur"] == pytest.approx(0.2)


def test_change_distribution_pools_by_group() -> None:
    from dashboard.advanced import change_distribution
    a = LEAF_PARTITION[0][0]   # treat as exposed
    c = LEAF_PARTITION[1][0]   # other
    # monthly series so 12-month windows exist
    dates = pd.date_range("2022-01-31", "2024-12-31", freq="ME")
    rows = []
    for i, dt in enumerate(dates):
        rows.append((a, dt.strftime("%Y-%m-%d"), 100.0 + i))     # rising
        rows.append((c, dt.strftime("%Y-%m-%d"), 100.0 - i))     # falling
    obs = pd.DataFrame({"series_id": [r[0] for r in rows],
                        "date": [pd.Timestamp(r[1]) for r in rows],
                        "value": [r[2] for r in rows]})
    dist = change_distribution(obs, exposed_ids=[a], other_ids=[c], since="2023-01", window=12)
    assert set(dist["group"].unique()) == {"AI-exposed", "Other"}
    assert (dist[dist["group"] == "AI-exposed"]["pct"] > 0).all()
    assert (dist[dist["group"] == "Other"]["pct"] < 0).all()


def test_exposure_industry_change_joins_aiie() -> None:
    a, b, naics_a = LEAF_PARTITION[0]
    obs = _obs([(a, "2022-11-30", 100.0), (a, "2026-05-31", 90.0)])
    meta = _meta([{"series_id": a, "program": "CES", "label": b, "geo_level": "national",
                   "measure": "ces_01", "seasonal": "SA", "industry_naics": naics_a}])
    exposure = pd.DataFrame({"naics": [naics_a, "99"], "aiie": [1.2, -0.5]})
    out = exposure_industry_change(obs, meta, exposure, "2022-11", "2026-05")
    assert len(out) == 1
    assert out.iloc[0]["aiie"] == pytest.approx(1.2)
    assert out.iloc[0]["pct_change"] == pytest.approx(-10.0)
