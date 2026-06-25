"""Plotly figure builders. Light editorial theme; clay accent = AI signal."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard.i18n import t

# Semantic data palette (hex approximations of the OKLCH tokens used in CSS).
# Color is an ENCODING: clay = decline / AI-exposed, teal = growth, slate = neutral/baseline.
INK = "#26272e"
MUTED = "#8a8d99"
LINE = "#e9e9ee"        # crisp cool gridline on white
CLAY = "#c2613a"        # decline / AI-exposed
CLAY_SOFT = "#dca07f"
SLATE = "#5b6b8c"       # neutral / baseline
TEAL = "#3a78b5"        # growth / positive (blue; clay<->blue diverging, no green)
SAND = "#b9a06b"
PAPER = "rgba(0,0,0,0)"

_SERIF = "'Iowan Old Style', 'Palatino Linotype', Georgia, serif"
_SANS = "Inter, 'Segoe UI', system-ui, sans-serif"

# Major postwar US recessions (NBER), for context shading.
RECESSIONS = [
    ("1948-11-01", "1949-10-31"), ("1953-07-01", "1954-05-31"),
    ("1957-08-01", "1958-04-30"), ("1960-04-01", "1961-02-28"),
    ("1969-12-01", "1970-11-30"), ("1973-11-01", "1975-03-31"),
    ("1980-01-01", "1980-07-31"), ("1981-07-01", "1982-11-30"),
    ("1990-07-01", "1991-03-31"), ("2001-03-01", "2001-11-30"),
    ("2007-12-01", "2009-06-30"), ("2020-02-01", "2020-04-30"),
]
CHATGPT = pd.Timestamp("2022-11-30")


def _template(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        font=dict(family=_SANS, size=13, color=INK),
        paper_bgcolor=PAPER,
        plot_bgcolor=PAPER,
        margin=dict(l=56, r=24, t=12, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=12)),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=LINE,
                        font=dict(family=_SANS, color=INK)),
        xaxis=dict(showgrid=False, linecolor=LINE, ticks="outside",
                   tickcolor=LINE, zeroline=False),
        yaxis=dict(gridcolor=LINE, zeroline=False, linecolor=PAPER),
    )
    return fig


def _recession_shading(fig: go.Figure, x0_min: pd.Timestamp) -> None:
    for start, end in RECESSIONS:
        if pd.Timestamp(end) < x0_min:
            continue
        fig.add_vrect(x0=start, x1=end, fillcolor=INK, opacity=0.05,
                      line_width=0, layer="below")


def _chatgpt_marker(fig: go.Figure, lang: str = "es") -> None:
    fig.add_vline(x=CHATGPT, line=dict(color=CLAY, width=1.4, dash="dot"))
    fig.add_annotation(x=CHATGPT, yref="paper", y=1.0, text=t("ChatGPT (Nov 2022)", lang),
                       showarrow=False, font=dict(color=CLAY, size=11),
                       xanchor="left", xshift=6, yanchor="top")


def fig_unemployment(ur: pd.DataFrame, lang: str = "es") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ur["date"], y=ur["value"], mode="lines",
                             line=dict(color=INK, width=1.6), name=t("U-3", lang),
                             hovertemplate="%{x|%b %Y}: %{y:.1f}%<extra></extra>"))
    if not ur.empty:
        _recession_shading(fig, ur["date"].min())
    _chatgpt_marker(fig, lang)
    fig.update_yaxes(ticksuffix="%")
    return _template(fig, 380)


def fig_education(edu: pd.DataFrame, lang: str = "es") -> go.Figure:
    fig = go.Figure()
    series = [
        ("less_than_hs", t("Less than high school", lang), CLAY, 1.4),
        ("high_school", t("High school, no college", lang), CLAY_SOFT, 1.4),
        ("some_college", t("Some college / associate", lang), SLATE, 1.4),
        ("bachelors_plus", t("Bachelor's and higher", lang), TEAL, 2.0),
    ]
    for col, label, color, width in series:
        if col in edu.columns:
            fig.add_trace(go.Scatter(x=edu["date"], y=edu[col], mode="lines",
                                     line=dict(color=color, width=width), name=label,
                                     hovertemplate=f"{label}<br>%{{x|%b %Y}}: %{{y:.1f}}%<extra></extra>"))
    _chatgpt_marker(fig, lang)
    fig.update_yaxes(ticksuffix="%")
    return _template(fig, 420)


def fig_sector_index(idx: pd.DataFrame, lang: str = "es") -> go.Figure:
    fig = go.Figure()
    palette = {"Total nonfarm": INK, "Information": CLAY,
               "Professional & business services": SLATE}
    widths = {"Total nonfarm": 1.6, "Information": 2.4,
              "Professional & business services": 1.8}
    for col in [c for c in idx.columns if c != "date"]:
        fig.add_trace(go.Scatter(x=idx["date"], y=idx[col], mode="lines",
                                 line=dict(color=palette.get(col, MUTED),
                                           width=widths.get(col, 1.6)),
                                 name=col,
                                 hovertemplate=f"{col}<br>%{{x|%b %Y}}: %{{y:.1f}}<extra></extra>"))
    fig.add_hline(y=100, line=dict(color=MUTED, width=1, dash="dash"))
    fig.update_yaxes(title=t("Index, Nov 2022 = 100", lang))
    fig.update_xaxes(range=["2019-01-01", str(idx["date"].max().date()) if not idx.empty else None])
    return _template(fig, 420)


def fig_jolts(total: pd.DataFrame, info: pd.DataFrame, lang: str = "es") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=total["date"], y=total["openings"], mode="lines",
                             line=dict(color=SLATE, width=1.8), name=t("Openings (total nonfarm)", lang),
                             hovertemplate=f"{t('Openings', lang)}<br>%{{x|%b %Y}}: %{{y:,.0f}}k<extra></extra>"))
    fig.add_trace(go.Scatter(x=total["date"], y=total["hires"], mode="lines",
                             line=dict(color=INK, width=1.6), name=t("Hires (total nonfarm)", lang),
                             hovertemplate=f"{t('Hires', lang)}<br>%{{x|%b %Y}}: %{{y:,.0f}}k<extra></extra>"))
    if not info.empty:
        fig.add_trace(go.Scatter(x=info["date"], y=info["openings"], mode="lines",
                                 line=dict(color=CLAY, width=1.8, dash="solid"),
                                 name=t("Openings (Information)", lang), yaxis="y2",
                                 hovertemplate=f"{t('Info openings', lang)}<br>%{{x|%b %Y}}: %{{y:,.0f}}k<extra></extra>"))
    _chatgpt_marker(fig, lang)
    fig.update_layout(yaxis=dict(title=t("Total nonfarm (000s)", lang), gridcolor=LINE),
                      yaxis2=dict(title=t("Information (000s)", lang), overlaying="y",
                                  side="right", showgrid=False, color=CLAY))
    return _template(fig, 420)


def fig_state_map(states: pd.DataFrame, lang: str = "es") -> go.Figure:
    states = states[states["abbr"] != "PR"]
    fig = go.Figure(go.Choropleth(
        locations=states["abbr"], z=states["ur"], locationmode="USA-states",
        colorscale=[[0, "#eef0f3"], [0.5, CLAY_SOFT], [1, CLAY]],
        marker_line_color="#ffffff", marker_line_width=0.6,
        colorbar=dict(title=t("UR %", lang), thickness=12, len=0.7, outlinewidth=0),
        text=states["name"],
        hovertemplate="%{text}: %{z:.1f}%<extra></extra>"))
    fig.update_layout(geo=dict(scope="usa", bgcolor=PAPER, lakecolor=PAPER,
                               landcolor="#eef0f3", subunitcolor="#ffffff"),
                      margin=dict(l=0, r=0, t=0, b=0), height=420,
                      font=dict(family=_SANS, color=INK), paper_bgcolor=PAPER)
    return fig


def fig_tightness(df: pd.DataFrame, lang: str = "es") -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df["ratio"], mode="lines",
                             line=dict(color=INK, width=1.6),
                             name=t("Unemployed per opening", lang),
                             hovertemplate="%{x|%b %Y}: %{y:.2f}<extra></extra>"))
    fig.add_hline(y=1.0, line=dict(color=CLAY, width=1, dash="dash"),
                  annotation_text=t("balance (1.0)", lang), annotation_font_color=CLAY)
    _chatgpt_marker(fig, lang)
    return _template(fig, 360)


def fig_industry_change(df: pd.DataFrame, value_col: str = "chg_since_chatgpt_pct",
                        title: str | None = None, lang: str = "es") -> go.Figure:
    """Horizontal leaderboard of industry employment change; clay = decline."""
    if title is None:
        title = t("% change since Nov 2022", lang)
    d = df.dropna(subset=[value_col]).sort_values(value_col)
    colors = [CLAY if v < 0 else SLATE for v in d[value_col]]
    fig = go.Figure(go.Bar(
        x=d[value_col], y=d["label"], orientation="h", marker_color=colors,
        marker_line_width=0,
        hovertemplate="%{y}: %{x:+.1f}%<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=MUTED, width=1))
    fig.update_xaxes(title=title, ticksuffix="%")
    height = max(360, 26 * len(d) + 80)
    return _template(fig, height)


def fig_education_distribution(dist: pd.DataFrame, lang: str = "es") -> go.Figure:
    """100% stacked area of employment share by educational attainment over time."""
    order = ["less_than_hs", "high_school", "some_college", "bachelors_plus"]
    labels = {"less_than_hs": t("Less than high school", lang), "high_school": t("High school", lang),
              "some_college": t("Some college / associate", lang), "bachelors_plus": t("Bachelor's and higher", lang)}
    colors = {"less_than_hs": CLAY, "high_school": CLAY_SOFT,
              "some_college": SLATE, "bachelors_plus": TEAL}
    fig = go.Figure()
    for edu in order:
        sub = dist[dist["education"] == edu].sort_values("date")
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["date"], y=sub["share"] * 100, mode="lines", stackgroup="one",
            name=labels[edu], line=dict(width=0.5, color=colors[edu]),
            fillcolor=colors[edu], hovertemplate=f"{labels[edu]}<br>%{{x|%Y}}: %{{y:.1f}}%<extra></extra>"))
    _chatgpt_marker(fig, lang)
    fig.update_yaxes(title=t("Share of employment", lang), ticksuffix="%", range=[0, 100])
    return _template(fig, 420)


def fig_occupation(occ: pd.DataFrame, lang: str = "es") -> go.Figure:
    occ = occ.copy()
    occ["short"] = occ["label"].str.replace(r":.*$", "", regex=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=occ["employment"], y=occ["gpts_beta"], mode="markers+text",
        text=occ["short"], textposition="top center",
        textfont=dict(size=11, color=INK),
        marker=dict(size=(occ["employment"] ** 0.5) / 40 + 8,
                    color=occ["gpts_beta"], colorscale=[[0, TEAL], [1, CLAY]],
                    cmin=0, cmax=1, opacity=0.85, line=dict(color="#ffffff", width=1),
                    colorbar=dict(title=t("LLM exp", lang), thickness=11, len=0.5, outlinewidth=0)),
        hovertemplate=f"%{{text}}<br>{t('employment', lang)}: %{{x:,.0f}}<br>{t('LLM exposure (beta)', lang)}: %{{y:.2f}}<extra></extra>"))
    fig.update_xaxes(type="log", title=t("Employment (log scale)", lang))
    fig.update_yaxes(title=t("LLM exposure (GPTs beta)", lang))
    return _template(fig, 440)
