"""Assemble the chart figures into one self-contained light HTML dashboard."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from dashboard import charts, prepare
from unemployment_pipeline.datasets import read_dataset

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"


@dataclass(frozen=True)
class Section:
    id: str
    eyebrow: str
    title: str
    caption: str
    chart_html: str


def _css() -> str:
    return """
:root{
  --paper: oklch(0.995 0.0015 250);   /* near-white page */
  --surface: oklch(0.982 0.004 250);  /* faint cool band for alternating sections */
  --ink: oklch(0.24 0.015 258);
  --muted: oklch(0.50 0.02 258);
  --faint: oklch(0.66 0.015 258);
  --line: oklch(0.915 0.004 258);
  --clay: oklch(0.58 0.13 42);         /* DATA: decline / AI-exposed */
  --clay-strong: oklch(0.50 0.16 40);  /* identity + section headers */
  --teal: oklch(0.54 0.10 248);        /* DATA: growth / positive (blue) */
  --slate: oklch(0.52 0.07 250);       /* DATA: neutral / baseline */
  --serif: 'Iowan Old Style','Palatino Linotype',Georgia,'Times New Roman',serif;
  --sans: Inter,'Segoe UI',system-ui,-apple-system,sans-serif;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.55;-webkit-font-smoothing:antialiased;
}
a{color:var(--clay-strong);text-decoration:none}
.wrap{max-width:1080px;margin:0 auto;padding:0 28px}

header.hero{padding:72px 0 36px;border-bottom:1px solid var(--line)}
.kicker{font-family:var(--sans);font-size:.78rem;letter-spacing:.16em;
  text-transform:uppercase;color:var(--clay-strong);font-weight:600;margin:0 0 14px}
h1{font-family:var(--serif);font-weight:600;font-size:clamp(2.3rem,5.2vw,3.7rem);
  line-height:1.04;letter-spacing:-.01em;margin:0 0 18px;max-width:18ch}
.lede{font-size:1.18rem;color:var(--muted);max-width:62ch;margin:0}

.kpis{display:flex;flex-wrap:wrap;gap:38px 52px;padding:30px 0 8px}
.kpi{display:flex;flex-direction:column;gap:2px}
.kpi .v{font-family:var(--serif);font-size:2.0rem;line-height:1;font-weight:600}
.kpi .l{font-size:.82rem;color:var(--muted);letter-spacing:.01em}
.kpi.flag .v{color:var(--clay-strong)}

nav.toc{position:sticky;top:0;z-index:5;background:oklch(0.995 0.0015 250 / 0.88);
  backdrop-filter:saturate(1.1) blur(6px);border-bottom:1px solid var(--line)}
nav.toc .wrap{display:flex;gap:26px;overflow-x:auto;padding-top:13px;padding-bottom:13px}
nav.toc a{font-size:.85rem;color:var(--muted);white-space:nowrap;font-weight:500}
nav.toc a:hover{color:var(--ink)}

section.exhibit{padding:62px 0;border-bottom:1px solid var(--line)}
section.exhibit:nth-child(even){background:var(--surface)}
.eyebrow{font-size:.76rem;letter-spacing:.14em;text-transform:uppercase;
  color:var(--clay-strong);font-weight:600;margin:0 0 10px}
section.exhibit h2{font-family:var(--serif);font-weight:600;color:var(--clay-strong);
  font-size:clamp(1.5rem,3vw,2.1rem);line-height:1.12;margin:0 0 14px;max-width:24ch}
.caption{color:var(--muted);max-width:70ch;margin:0 0 28px;font-size:1.02rem}
.caption b{color:var(--ink);font-weight:600}
.chart{background:transparent}

/* JS-gated: without JS, content is always visible (progressive enhancement). */
html.js .fade{opacity:0;transform:translateY(14px)}
html.js .fade.in{opacity:1;transform:none;transition:opacity .7s cubic-bezier(.22,1,.36,1),
  transform .7s cubic-bezier(.22,1,.36,1)}
@media (prefers-reduced-motion:reduce){html.js .fade{opacity:1;transform:none}}

footer{padding:54px 0 80px;color:var(--faint);font-size:.85rem}
footer .note{max-width:74ch;margin:0 0 14px}
footer b{color:var(--muted)}
.disclaimer{background:var(--surface);border:1px solid var(--line);border-radius:10px;
  padding:18px 22px;max-width:74ch;color:var(--muted);font-size:.92rem;margin:0 0 26px}
"""


def _nav(sections: list[Section]) -> str:
    links = "".join(f'<a href="#{s.id}">{s.title}</a>' for s in sections)
    return f'<nav class="toc"><div class="wrap">{links}</div></nav>'


def _kpis(kpis: dict[str, str], flagged: Optional[set[str]] = None) -> str:
    flagged = flagged or set()
    items = ""
    for label, value in kpis.items():
        cls = "kpi flag" if label in flagged else "kpi"
        items += f'<div class="{cls}"><span class="v">{value}</span><span class="l">{label}</span></div>'
    return f'<div class="wrap"><div class="kpis">{items}</div></div>'


def _section_html(s: Section) -> str:
    return f"""
<section class="exhibit" id="{s.id}"><div class="wrap fade">
  <p class="eyebrow">{s.eyebrow}</p>
  <h2>{s.title}</h2>
  <p class="caption">{s.caption}</p>
  <div class="chart">{s.chart_html}</div>
</div></section>"""


def build_html_document(
    title: str,
    subtitle: str,
    kpis: dict[str, str],
    sections: list[Section],
    asof: str,
    flagged_kpis: Optional[set[str]] = None,
    sources: str = (
        "Bureau of Labor Statistics (CPS, LAUS, CES, JOLTS, OEWS). "
        "AI-exposure scores: Eloundou, Manning, Mishkin & Rock (2023), GPTs are GPTs; "
        "Felten, Raj & Seamans, AI Occupational Exposure."
    ),
) -> str:
    nav = _nav(sections)
    body_sections = "".join(_section_html(s) for s in sections)
    motion = (
        "<script>const io=new IntersectionObserver((es)=>es.forEach(e=>{"
        "if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),"
        "{threshold:0.12});const fades=document.querySelectorAll('.fade');"
        "fades.forEach(el=>io.observe(el));"
        "setTimeout(()=>fades.forEach(el=>el.classList.add('in')),2500);</script>"
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="{PLOTLY_CDN}" charset="utf-8"></script>
<style>{_css()}</style>
<script>document.documentElement.classList.add('js');</script>
</head><body>
<header class="hero"><div class="wrap">
  <p class="kicker">{subtitle}</p>
  <h1>{title}</h1>
  <p class="lede">A granular read of the US labor market from Bureau of Labor Statistics
  data, asking whether generative AI has begun to displace work since ChatGPT launched
  in November 2022. Data through {asof}.</p>
</div></header>
{_kpis(kpis, flagged_kpis)}
{nav}
{body_sections}
<footer><div class="wrap">
  <div class="disclaimer"><b>Read with care.</b> These exhibits show correlation, not
  causation. A divergence that coincides with AI adoption is not proof AI caused it;
  business cycles, interest rates, post-pandemic normalization, and sector-specific
  shocks all move these series. Treat the patterns as hypotheses to test, not verdicts.</div>
  <p class="note"><b>Sources.</b> {sources}</p>
  <p class="note">Built with a reproducible BLS pipeline. Series verified against the
  BLS Public Data API v2. As of {asof}.</p>
</div></footer>
{motion}
</body></html>"""


# --------------------------------------------------------------------------- #
# Data wiring
# --------------------------------------------------------------------------- #

def _fig_html(fig, div_id: str) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       div_id=div_id, config={"displaylogo": False, "responsive": True})


def _fmt(v: Optional[float], suffix: str = "", digits: int = 1) -> str:
    return "n/a" if v is None else f"{v:.{digits}f}{suffix}"


def build_dashboard(cache_dir: Path = Path("data/cache"),
                    out_path: Path = Path("output/dashboard.html")) -> Path:
    obs = prepare.load_observations(cache_dir)
    meta = read_dataset("series_meta", cache_dir)
    occ_exp = read_dataset("exposure_occupation", cache_dir)

    ur = prepare.ur_timeseries(obs)
    edu = prepare.education_gradient(obs)
    idx = prepare.ai_sector_index(obs)
    jolts_total = prepare.jolts_openings_hires(obs, "000000")
    jolts_info = prepare.jolts_openings_hires(obs, "510000")
    states = prepare.state_latest_ur(obs)
    tight = prepare.tightness_ratio(obs)
    occ = prepare.occupation_exposure(obs, meta, occ_exp)
    k = prepare.national_kpis(obs)

    # dynamic caption numbers
    info_chg = None
    if not idx.empty and "Information" in idx.columns:
        info_chg = idx["Information"].dropna().iloc[-1] - 100
    total_chg = None
    if not idx.empty and "Total nonfarm" in idx.columns:
        total_chg = idx["Total nonfarm"].dropna().iloc[-1] - 100
    gap_pre = edu[(edu.date >= "2019-01-01") & (edu.date < "2022-11-30")]["gap_hs_minus_bach"].mean() \
        if "gap_hs_minus_bach" in edu.columns else None
    gap_post = edu[edu.date >= "2023-01-01"]["gap_hs_minus_bach"].mean() \
        if "gap_hs_minus_bach" in edu.columns else None
    asof = obs["date"].max().strftime("%B %Y")

    kpis = {
        "Unemployment rate": _fmt(k["unemployment_rate"], "%"),
        "Labor force participation": _fmt(k["lfpr"], "%"),
        "Bachelor's+ UR": _fmt(k["ur_bachelors"], "%"),
        "Job openings": _fmt(k["openings"], "k", 0),
        "Hires": _fmt(k["hires"], "k", 0),
        "Quits rate": _fmt(k["quits_rate"], "%"),
    }

    industry_chg = prepare.industry_employment_change(obs, meta)
    edu_dist = prepare.education_distribution(obs, meta)
    jolts_ind = prepare.jolts_industry_change(obs, meta)
    # leaderboards: drop overlapping aggregate rollups, keep distinct sectors
    if not industry_chg.empty and "is_aggregate" in industry_chg.columns:
        industry_chg = industry_chg[~industry_chg["is_aggregate"]].reset_index(drop=True)
    if not jolts_ind.empty and "is_aggregate" in jolts_ind.columns:
        jolts_ind = jolts_ind[~jolts_ind["is_aggregate"]].reset_index(drop=True)

    def _names(df: pd.DataFrame, col: str, asc: bool, n: int) -> list[str]:
        if df.empty or col not in df.columns:
            return []
        d = df.dropna(subset=[col]).sort_values(col, ascending=asc)
        return [str(x) for x in d["label"].head(n).tolist()]

    ind_worst = _names(industry_chg, "chg_since_chatgpt_pct", True, 2)
    ind_best = _names(industry_chg, "chg_since_chatgpt_pct", False, 1)
    jo_worst = _names(jolts_ind, "openings_chg_since_chatgpt_pct", True, 2)
    edu_latest = edu_dist[edu_dist["date"] == edu_dist["date"].max()] if not edu_dist.empty else edu_dist

    def _share(edu: str) -> str:
        r = edu_latest[edu_latest["education"] == edu]["share"] if not edu_latest.empty else []
        return _fmt(float(r.iloc[0]) * 100, "%") if len(r) else "n/a"

    # (id, title, caption, figure, show?)
    candidates = [
        ("headline", "The headline unemployment rate stays low",
         "The U-3 rate sits near <b>" + _fmt(k['unemployment_rate'], '%') + "</b>, low by "
         "historical standards. A single number hides the structural shifts underneath, which "
         "is where any AI signal would first appear. Shaded bands mark NBER recessions.",
         charts.fig_unemployment(ur), True),
        ("education", "The education premium is compressing",
         "Higher education has always meant lower unemployment. That protective gap (high school "
         "minus bachelor's) averaged <b>" + _fmt(gap_pre, 'pp') + "</b> in 2019 to 2022 and <b>" +
         _fmt(gap_post, 'pp') + "</b> since 2023. Generative AI is unusual in targeting cognitive, "
         "white collar tasks, so a narrowing premium is a structural signal worth watching.",
         charts.fig_education(edu), True),
        ("edu-dist", "The workforce keeps tilting toward graduates",
         "Share of total employment by educational attainment. Workers with a bachelor's degree or "
         "higher now hold <b>" + _share('bachelors_plus') + "</b> of all jobs, against <b>" +
         _share('less_than_hs') + "</b> for those without a high school diploma. The graduate share, "
         "where AI exposure concentrates, keeps rising.",
         charts.fig_education_distribution(edu_dist), not edu_dist.empty),
        ("sectors", "Information employment has fallen since ChatGPT",
         "Indexed to 100 at the ChatGPT launch, total nonfarm payrolls grew about <b>" +
         _fmt(total_chg, 'pp', 1) + "</b> while the <b>Information</b> sector, the most AI-exposed "
         "supersector, fell roughly <b>" + _fmt(info_chg, 'pp', 1) + "</b>. Professional and business "
         "services has been roughly flat. The divergence is striking, though tech hiring also "
         "unwound a pandemic over-expansion.",
         charts.fig_sector_index(idx), True),
        ("industries", "Which sectors are changing most",
         "Every industry ranked by payroll-employment change since ChatGPT. " +
         (("Declines run deepest in <b>" + " and ".join(ind_worst) + "</b>; the strongest gains are "
           "in <b>" + (ind_best[0] if ind_best else "n/a") + "</b>. ") if ind_worst else "") +
         "Sorting all sectors this way shows where the labor market is actually shifting, not just "
         "the average.",
         charts.fig_industry_change(industry_chg), len(industry_chg) >= 3),
        ("flows", "Hiring has cooled faster than layoffs have risen",
         "Job openings and hires capture labor demand directly. A falling-openings, low-layoff "
         "pattern reads as a hiring freeze rather than a wave of cuts, which is how AI displacement "
         "could first surface. The right axis tracks Information openings.",
         charts.fig_jolts(jolts_total, jolts_info), True),
        ("jolts-industry", "Where hiring demand has dried up",
         "Job openings change by industry since ChatGPT. " +
         (("Openings have fallen most in <b>" + " and ".join(jo_worst) + "</b>. ") if jo_worst else "") +
         "Openings lead payrolls, so this is an early read on which sectors are pulling back.",
         charts.fig_industry_change(jolts_ind, "openings_chg_since_chatgpt_pct",
                                    "Openings % change since Nov 2022"), len(jolts_ind) >= 3),
        ("occupations", "The most AI-exposed occupations",
         "Each point is a detailed occupation, placed by its employment (horizontal) and its "
         "exposure to large language models (vertical, from the GPTs are GPTs study). Data entry, "
         "writing, and software development score highest. Tracking employment in these roles is the "
         "cleanest occupation-level test.",
         charts.fig_occupation(occ), not occ.empty),
        ("geography", "Where the labor market is tight or slack",
         "AI-exposed work clusters in a handful of metros, so the national rate masks local "
         "divergence. Latest seasonally adjusted state unemployment rates.",
         charts.fig_state_map(states), not states.empty),
        ("tightness", "Labor-market tightness has normalized",
         "Unemployed workers per job opening. Below 1.0 the market favors workers, above 1.0 it "
         "favors employers. The ratio has drifted back toward balance as openings receded from their "
         "2022 peak.",
         charts.fig_tightness(tight), not tight.empty),
    ]

    sections = []
    exhibit_n = 0
    for sid, title, caption, fig, show in candidates:
        if not show:
            continue
        exhibit_n += 1
        sections.append(Section(sid, f"Exhibit {exhibit_n}", title, caption,
                                _fig_html(fig, f"c-{sid}")))

    html = build_html_document(
        title="Has AI taken a toll on jobs?",
        subtitle="US labor market, a BLS data view",
        kpis=kpis, sections=sections, asof=asof,
        flagged_kpis={"Bachelor's+ UR"},
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    path = build_dashboard()
    print(f"Dashboard written to {path}")
