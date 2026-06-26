"""Advanced/creative chart builders: heatmap, boxplot, animated choropleth."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard.charts import (CLAY, CLAY_SOFT, INK, LINE, MUTED, PAPER, SAND, SLATE, TEAL,
                              _SANS, _chatgpt_marker, _template)
from dashboard.i18n import t

_DIVERGING = [[0.0, CLAY], [0.5, "#f3f4f6"], [1.0, TEAL]]
CHATGPT = pd.Timestamp("2022-11-30")
GPT4 = pd.Timestamp("2023-03-31")


def fig_industry_heatmap(matrix: dict, lang: str = "es") -> go.Figure:
    """Horizontal heatmap of YoY % employment change: industries (narrow columns) x year (rows)."""
    industries = matrix["industries"]
    industries_disp = [t(name, lang) for name in industries]
    years = [str(y) for y in matrix["years"]]
    z = matrix["z"]  # [industry][year]
    zt = [[z[i][j] for i in range(len(industries))] for j in range(len(years))]  # [year][industry]
    fig = go.Figure(go.Heatmap(
        z=zt, x=industries_disp, y=years, colorscale=_DIVERGING, zmid=0, zmin=-10, zmax=10,
        xgap=1, ygap=2,
        colorbar=dict(title=t("YoY %", lang), thickness=12, len=0.7, outlinewidth=0),
        hovertemplate="%{x}<br>%{y}: %{z:+.1f}%<extra></extra>"))
    fig.update_layout(
        template="plotly_white", paper_bgcolor=PAPER, plot_bgcolor=PAPER,
        font=dict(family=_SANS, size=11, color=INK),
        margin=dict(l=8, r=8, t=8, b=8),
        height=34 * len(years) + 200,
        xaxis=dict(side="bottom", showgrid=False, tickangle=-45, automargin=True),
        yaxis=dict(showgrid=False, autorange="reversed", automargin=True))
    return fig


def fig_state_ur_boxplot(df: pd.DataFrame, lang: str = "es") -> go.Figure:
    """Distribution of statewide unemployment rates across states, one box per year."""
    d = df.dropna(subset=["ur"]).copy()
    d["yr"] = d["year"].astype(str)
    fig = go.Figure(go.Box(
        x=d["yr"], y=d["ur"], marker_color=CLAY, line_color=SLATE,
        boxpoints="outliers", marker=dict(size=4, color=SLATE, opacity=0.6),
        fillcolor="rgba(194,97,58,0.12)",
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>"))
    fig.update_yaxes(title=t("Statewide unemployment rate", lang), ticksuffix="%")
    fig.update_xaxes(title="")
    return _template(fig, 420)


def fig_state_ur_choropleth_animated(df: pd.DataFrame, lang: str = "es") -> go.Figure:
    """Animated US choropleth of statewide UR with a year slider and play button."""
    d = df[df["abbr"] != "PR"].dropna(subset=["ur"]).copy()
    years = sorted(d["year"].unique())
    zmax = float(d["ur"].quantile(0.97))

    def frame_data(year: int) -> go.Choropleth:
        s = d[d["year"] == year]
        return go.Choropleth(
            locations=s["abbr"], z=s["ur"], locationmode="USA-states",
            colorscale=[[0, "#eef0f3"], [0.5, "#dca07f"], [1, CLAY]],
            zmin=2, zmax=zmax, marker_line_color="#ffffff", marker_line_width=0.5,
            colorbar=dict(title=t("UR %", lang), thickness=12, len=0.7, outlinewidth=0),
            text=s["name"], hovertemplate="%{text}: %{z:.1f}%<extra></extra>")

    fig = go.Figure(
        data=[frame_data(years[-1])],
        frames=[go.Frame(data=[frame_data(y)], name=str(y)) for y in years])
    steps = [dict(method="animate", label=str(y),
                  args=[[str(y)], dict(mode="immediate", frame=dict(duration=0, redraw=True),
                                       transition=dict(duration=0))]) for y in years]
    fig.update_layout(
        geo=dict(scope="usa", bgcolor=PAPER, lakecolor=PAPER, landcolor="#eef0f3",
                 subunitcolor="#ffffff"),
        margin=dict(l=0, r=0, t=10, b=0), height=460,
        font=dict(family=_SANS, color=INK), paper_bgcolor=PAPER,
        sliders=[dict(active=len(years) - 1, currentvalue=dict(prefix=t("Year:", lang) + " "),
                      pad=dict(t=30), steps=steps)],
        updatemenus=[dict(type="buttons", showactive=False, x=0.02, y=1.05,
                          buttons=[dict(label=t("Play", lang), method="animate",
                                        args=[None, dict(frame=dict(duration=420, redraw=True),
                                                         fromcurrent=True,
                                                         transition=dict(duration=120))]),
                                   dict(label=t("Pause", lang), method="animate",
                                        args=[[None], dict(mode="immediate",
                                                           frame=dict(duration=0, redraw=False))])])])
    return fig


def fig_event_study(es: pd.DataFrame, lang: str = "es",
                    pretrend: dict | None = None) -> go.Figure:
    """Treated (Information) vs control, indexed to 100 at the ChatGPT anchor.

    When ``pretrend`` (from ``advanced.event_pretrend``) is supplied, overlays the
    pre-2020 trend projected forward as a dotted counterfactual with a 95%
    prediction band, shades the COVID window excluded from the fit, and marks the
    first month the observed gap leaves the band. Labels are descriptive; the
    chart shows the test, it does not assert a cause.
    """
    fig = go.Figure()
    # Clip the observed traces to the analysis window so autoscale (double-click)
    # lands on the relevant period instead of the full 1939+ indexed history.
    if not es.empty:
        es = es[es["date"] >= pd.Timestamp("2014-01-01")]
    # pre-trend counterfactual band + dotted line (added first -> sits behind)
    if pretrend is not None and not pretrend["frame"].empty:
        proj = pretrend["frame"]
        proj = proj[proj["date"] >= pd.Timestamp("2020-01-01")]
        band_name = t("Projected pre-2020 trend (95% prediction band)", lang)
        fig.add_trace(go.Scatter(x=proj["date"], y=proj["cf_hi"], mode="lines",
                                 line=dict(width=0), hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=proj["date"], y=proj["cf_lo"], mode="lines",
                                 line=dict(width=0), fill="tonexty",
                                 fillcolor="rgba(138,141,153,0.16)", hoverinfo="skip",
                                 name=band_name))
        fig.add_trace(go.Scatter(
            x=proj["date"], y=proj["cf_idx"], mode="lines",
            line=dict(color=MUTED, width=1.6, dash="dot"),
            name=t("Information (pre-2020 counterfactual)", lang),
            hovertemplate=f"{t('Counterfactual', lang)} %{{x|%b %Y}}: %{{y:.1f}}<extra></extra>"))
    if "control" in es.columns:
        fig.add_trace(go.Scatter(x=es["date"], y=es["control"], mode="lines",
                                 line=dict(color=SLATE, width=1.8), name=t("Control (total private ex-Info)", lang),
                                 hovertemplate=f"{t('Control', lang)} %{{x|%b %Y}}: %{{y:.1f}}<extra></extra>"))
    fig.add_trace(go.Scatter(x=es["date"], y=es["treated"], mode="lines",
                             line=dict(color=CLAY, width=2.4), name=t("Information (treated)", lang),
                             hovertemplate=f"{t('Information', lang)} %{{x|%b %Y}}: %{{y:.1f}}<extra></extra>"))
    fig.add_hline(y=100, line=dict(color=MUTED, width=1, dash="dash"))
    fig.add_vline(x=CHATGPT, line=dict(color=INK, width=1.2, dash="dot"))
    fig.add_annotation(x=CHATGPT, yref="paper", y=1.0, text=t("ChatGPT", lang),
                       showarrow=False, font=dict(color=INK, size=11), xanchor="left", xshift=5)
    fig.add_vline(x=GPT4, line=dict(color=MUTED, width=1, dash="dot"))
    if pretrend is not None:
        fig.add_vrect(x0="2020-01-01", x1="2021-12-31", fillcolor="rgba(120,120,130,0.10)",
                      line_width=0, layer="below")
        fig.add_annotation(x=pd.Timestamp("2021-01-01"), yref="paper", y=0.06,
                           text=t("Excluded from fit (COVID)", lang), showarrow=False,
                           font=dict(color=MUTED, size=9), xanchor="center")
        em = pretrend.get("exit_month")
        if em is not None:
            em = pd.Timestamp(em)
            fig.add_vline(x=em, line=dict(color=MUTED, width=1, dash="dash"))
            fig.add_annotation(x=em, yref="paper", y=0.0,
                               text=f"{t('Gap leaves band', lang)} · {em.strftime('%b %Y')}",
                               showarrow=False, font=dict(color=MUTED, size=10),
                               xanchor="right", xshift=-4)
    fig.update_yaxes(title=t("Employment, anchor = 100", lang))
    fig.update_xaxes(range=["2015-01-01", str(es["date"].max().date()) if not es.empty else None])
    return _template(fig, 440)


def fig_beveridge(bev: pd.DataFrame, lang: str = "es") -> go.Figure:
    """Connected Beveridge scatter: unemployment rate vs job-openings rate, time-colored."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=bev["u"], y=bev["v"], mode="lines+markers",
        marker=dict(size=5, color=bev["year"], colorscale=[[0, "#cfd6dd"], [1, "#26272e"]],
                    showscale=True, colorbar=dict(title=t("Year", lang), thickness=12, len=0.6, outlinewidth=0)),
        line=dict(color="rgba(140,140,150,0.45)", width=1),
        text=[d.strftime("%b %Y") for d in bev["date"]],
        hovertemplate=f"%{{text}}<br>{t('UR', lang)} %{{x:.1f}}%, {t('openings', lang)} %{{y:.1f}}%<extra></extra>"))
    for ts, lab in [(CHATGPT, t("ChatGPT", lang)), (GPT4, t("GPT-4", lang))]:
        row = bev[bev["date"] <= ts]
        if not row.empty:
            r = row.iloc[-1]
            fig.add_trace(go.Scatter(x=[r["u"]], y=[r["v"]], mode="markers+text", text=[lab],
                                     textposition="top right", marker=dict(size=10, color=INK),
                                     showlegend=False, hoverinfo="skip",
                                     textfont=dict(color=INK, size=11)))
    fig.update_xaxes(title=t("Unemployment rate", lang), ticksuffix="%")
    fig.update_yaxes(title=t("Job-openings rate", lang), ticksuffix="%")
    return _template(fig, 460)


def fig_dispersion_fan(disp: pd.DataFrame, lang: str = "es") -> go.Figure:
    """Cross-state UR percentile fan + labor-force-weighted std-dev (secondary axis)."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=disp["date"], y=disp["p90"], mode="lines", line=dict(width=0),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=disp["date"], y=disp["p10"], mode="lines", line=dict(width=0),
                             fill="tonexty", fillcolor="rgba(91,107,140,0.12)",
                             name=t("p10-p90 of states", lang), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=disp["date"], y=disp["p75"], mode="lines", line=dict(width=0),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=disp["date"], y=disp["p25"], mode="lines", line=dict(width=0),
                             fill="tonexty", fillcolor="rgba(91,107,140,0.22)",
                             name=t("p25-p75", lang), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=disp["date"], y=disp["p50"], mode="lines",
                             line=dict(color=INK, width=1.8), name=t("Median state", lang),
                             hovertemplate="%{x|%Y}: %{y:.1f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=disp["date"], y=disp["wstd"], mode="lines", yaxis="y2",
                             line=dict(color=CLAY, width=1.6), name=t("Dispersion (LF-wtd std)", lang),
                             hovertemplate=f"%{{x|%Y}}: {t('std', lang)} %{{y:.2f}}<extra></extra>"))
    fig.update_layout(yaxis=dict(title=t("State unemployment rate", lang), ticksuffix="%", gridcolor=LINE),
                      yaxis2=dict(title=t("Dispersion (pp)", lang), overlaying="y", side="right",
                                  showgrid=False, color=CLAY))
    return _template(fig, 420)


def fig_education_gap(gap: pd.DataFrame, lang: str = "es") -> go.Figure:
    """Filled gap = high-school minus bachelor's unemployment rate, with the AI anchor."""
    g = gap.dropna(subset=["gap_hs_minus_bach"]) if "gap_hs_minus_bach" in gap.columns else gap
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=g["date"], y=g["gap_hs_minus_bach"], mode="lines",
                             line=dict(color=CLAY, width=1.8), fill="tozeroy",
                             fillcolor="rgba(194,97,58,0.12)", name=t("HS minus bachelor's UR gap", lang),
                             hovertemplate="%{x|%b %Y}: %{y:.1f} pp<extra></extra>"))
    _chatgpt_marker(fig)
    fig.update_yaxes(title=t("Unemployment-rate gap (pp)", lang), ticksuffix=" pp")
    fig.update_xaxes(range=["2010-01-01", str(g["date"].max().date()) if not g.empty else None])
    return _template(fig, 380)


def fig_diffusion(di: pd.DataFrame, lang: str = "es") -> go.Figure:
    """Employment diffusion: share of industries growing (6-month), 50 = breadth-neutral."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=di["date"], y=di["diffusion"], mode="lines",
                             line=dict(color=INK, width=1.6), name=t("% industries growing", lang),
                             hovertemplate="%{x|%b %Y}: %{y:.0f}%<extra></extra>"))
    fig.add_hline(y=50, line=dict(color=MUTED, width=1, dash="dash"),
                  annotation_text=t("breadth-neutral", lang), annotation_font_color=MUTED)
    _chatgpt_marker(fig)
    fig.update_yaxes(title=t("Share of industries growing", lang), ticksuffix="%", range=[0, 100])
    fig.update_xaxes(range=["2015-01-01", str(di["date"].max().date()) if not di.empty else None])
    return _template(fig, 340)


def fig_change_histogram(cd, lang: str = "es") -> go.Figure:
    """Overlaid distribution of 12-month % employment changes: AI-exposed vs other."""
    fig = go.Figure()
    palette = {"AI-exposed": CLAY, "Other": SLATE}
    for group, color in palette.items():
        vals = cd[cd["group"] == group]["pct"]
        if vals.empty:
            continue
        label = t(group, lang)
        fig.add_trace(go.Histogram(x=vals, name=label, histnorm="probability density",
                                   marker_color=color, opacity=0.55, nbinsx=40,
                                   hovertemplate=label + ": %{x:.0f}%<extra></extra>"))
        fig.add_vline(x=float(vals.median()), line=dict(color=color, width=1.5, dash="dash"))
    fig.add_vline(x=0, line=dict(color=MUTED, width=1))
    fig.update_layout(barmode="overlay", legend=dict(orientation="h", y=1.02, x=0,
                                                      bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(title=t("12-month employment change (%)", lang), ticksuffix="%")
    fig.update_yaxes(title=t("Density", lang))
    return _template(fig, 400)
