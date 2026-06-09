"""Build the advanced interactive exploration dashboard.

A sticky baseline/compare date control recomputes four charts client-side
(waterfall, change distribution, exposure scatter, freeze-vs-cuts). The rest
are server-rendered (event-study, heatmap, diffusion, dispersion fan, education
gap, Beveridge curve, occupation bubble).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from dashboard import advanced, bundle, charts, charts_advanced, prepare
from dashboard.build import PLOTLY_CDN, _css
from unemployment_pipeline.datasets import read_dataset

_CONTROL_CSS = """
.controlbar{position:sticky;top:0;z-index:6;background:oklch(0.982 0.004 250 / 0.95);
  backdrop-filter:saturate(1.1) blur(6px);
  border-bottom:1px solid var(--line);box-shadow:0 1px 0 var(--line)}
.controlbar .wrap{display:flex;flex-wrap:wrap;align-items:center;gap:12px 20px;padding:15px 28px}
.controlbar .lab{font-family:var(--serif);font-size:1.05rem;color:var(--ink)}
.controlbar select{font-family:var(--sans);font-size:.92rem;color:var(--ink);background:var(--paper);
  border:1px solid var(--line);border-radius:8px;padding:6px 11px;cursor:pointer}
.controlbar .chips{display:flex;gap:6px}
.controlbar .preset{font-size:.78rem;border:1px solid var(--line);border-radius:999px;
  padding:5px 11px;background:var(--paper);cursor:pointer;color:var(--muted)}
.controlbar .preset:hover{border-color:var(--clay);color:var(--clay-strong)}
.controlbar .readout{margin-left:auto;font-size:.9rem;color:var(--muted)}
.controlbar .readout b{color:var(--clay-strong)}
.chip{display:inline-block;font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;
  color:var(--clay-strong);font-weight:600;border:1px solid var(--line);border-radius:999px;
  padding:3px 9px;margin-left:8px;vertical-align:middle}
.findings{padding:56px 0;border-bottom:1px solid var(--line);background:var(--surface)}
.findings .eyebrow{margin-bottom:16px}
.findings h2{font-family:var(--serif);font-weight:600;color:var(--clay-strong);font-size:clamp(1.6rem,3vw,2.2rem);margin:0 0 28px;max-width:24ch}
.findings ol{list-style:none;counter-reset:f;padding:0;margin:0;display:grid;
  grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:28px 44px}
.findings li{counter-increment:f;position:relative;padding-left:50px;max-width:58ch}
.findings li::before{content:counter(f,decimal-leading-zero);position:absolute;left:0;top:-6px;
  font-family:var(--serif);font-size:1.6rem;color:var(--clay-strong);font-weight:600}
.findings li b{color:var(--ink);font-weight:600}.findings li span{color:var(--muted);font-size:.97rem}
.subnote{font-size:.84rem;color:var(--faint);margin:18px 0 0}

.toolbar{background:var(--ink);color:var(--paper)}
.toolbar .wrap{display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px;padding:11px 28px}
.toolbar .brand{font-family:var(--serif);font-size:.98rem;margin-right:auto;color:var(--paper);opacity:.92}
.toolbar input{font-family:var(--sans);font-size:.85rem;padding:7px 11px;border-radius:8px;border:1px solid #4a4b54;
  background:#34353e;color:var(--paper);width:240px}
.toolbar input::placeholder{color:#9a9ca6}
.toolbar button{font-family:var(--sans);font-size:.85rem;font-weight:600;padding:7px 13px;border-radius:8px;
  border:1px solid #4a4b54;background:#34353e;color:var(--paper);cursor:pointer}
.toolbar button:hover{background:var(--clay-strong);border-color:var(--clay-strong)}
.toolbar button.primary{background:var(--clay);border-color:var(--clay)}
.toolbar button.primary:hover{background:var(--clay-strong)}

#overlay{position:fixed;inset:0;z-index:50;display:none;align-items:center;justify-content:center;
  background:oklch(0.26 0.02 255 / 0.78);backdrop-filter:blur(3px)}
#overlay.show{display:flex}
.loader{text-align:center;color:var(--paper);font-family:var(--sans)}
.loader .bars{display:flex;gap:7px;justify-content:center;align-items:flex-end;height:64px;margin-bottom:18px}
.loader .bars i{width:12px;background:var(--clay);border-radius:3px 3px 0 0;animation:grow 1s ease-in-out infinite}
.loader .bars i:nth-child(2){animation-delay:.15s;background:#dca07f}
.loader .bars i:nth-child(3){animation-delay:.3s;background:var(--slate)}
.loader .bars i:nth-child(4){animation-delay:.45s;background:#dca07f}
.loader .bars i:nth-child(5){animation-delay:.6s;background:var(--clay)}
@keyframes grow{0%,100%{height:14px}50%{height:62px}}
.loader .msg{font-size:1.05rem;font-weight:600}.loader .sub{font-size:.85rem;opacity:.7;margin-top:6px}

@media print{
  .toolbar,.controlbar,nav.toc,#overlay{display:none !important}
  body{font-size:12px}
  header.hero{padding:18px 0 8px} h1{font-size:2rem}
  section.exhibit{padding:18px 0;break-inside:avoid;page-break-inside:avoid}
  .findings{padding:18px 0}
  .fade{opacity:1 !important;transform:none !important}
}
"""

_FINDINGS = [
    ("Information employment peaked the month ChatGPT launched.",
     "Down 332,000 jobs (10.7%) from the November 2022 peak, yet only 3.7% below 2019. "
     "Most of the decline is post-ChatGPT. Move the baseline below to see it."),
    ("The verdict flips with your baseline.",
     "Software publishers are up 35% since 2019 but flat since late 2022. The date control turns "
     "that fragility into something you can test yourself."),
    ("More AI-exposed industries shrank more, but the fit is weak.",
     "The exposure-vs-change slope is negative yet explains little (R-squared near 0.04). "
     "Exposure is potential, not adoption; read it as suggestive, not proof."),
    ("Hiring froze and, in tech, turned to cuts.",
     "Information job openings fell 61% while its layoffs rose 43%, active cutting. Manufacturing "
     "shows the quieter low-hire, low-fire pattern instead."),
    ("The labor market round-tripped to balance.",
     "The Beveridge curve looped from historically overheated (2022) back toward normal, with "
     "openings per unemployed near 1.0."),
    ("The educated were not hit harder, in levels.",
     "The high-school-minus-bachelor's unemployment gap narrowed, but graduates kept the lower "
     "rate. A clean AI-displacement story would show otherwise."),
]


def _fig_html(fig, div_id: str) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False, div_id=div_id,
                       config={"displaylogo": False, "responsive": True})


def _fmt(v: Optional[float], suffix: str = "", digits: int = 1) -> str:
    return "n/a" if v is None else f"{v:.{digits}f}{suffix}"


def _findings_html() -> str:
    items = "".join(f"<li><b>{t}</b> <span>{d}</span></li>" for t, d in _FINDINGS)
    return ('<section class="findings" id="findings"><div class="wrap fade">'
            '<p class="eyebrow">What the full dataset says</p>'
            '<h2>Six findings from 900 series</h2>'
            f'<ol>{items}</ol></div></section>')


def _exhibit(n: int, sid: str, title: str, caption: str, body: str, interactive: bool) -> str:
    chip = '<span class="chip">interactive</span>' if interactive else ''
    return (f'<section class="exhibit" id="{sid}"><div class="wrap fade">'
            f'<p class="eyebrow">Exhibit {n}</p><h2>{title}{chip}</h2>'
            f'<p class="caption">{caption}</p>{body}</div></section>')


def build_interactive(cache_dir: Path = Path("data/cache"),
                      out_path: Path = Path("output/dashboard.html")) -> Path:
    obs = prepare.load_observations(cache_dir)
    meta = read_dataset("series_meta", cache_dir)
    occ_exp = read_dataset("exposure_occupation", cache_dir)
    exp_ind = read_dataset("exposure_industry", cache_dir)
    asof = obs["date"].max().strftime("%B %Y")

    # ---- embedded bundle for client-side recompute ----
    adv = advanced.advanced_bundle(obs, meta, exp_ind)
    months = sorted({d for s in adv["industries"] + adv["sectors"] for d in s["dates"]})
    base_default = "2022-11" if "2022-11" in months else months[len(months) // 2]
    compare_default = months[-1]
    data_json = json.dumps(adv)
    months_json = json.dumps(months)

    # ---- server-rendered figures ----
    es = advanced.event_study_indexed(obs, "2022-11", "CES5000000001", ["CES0500000001"])
    matrix = bundle.industry_year_matrix(
        obs, meta, only_ids={s for s, _, _ in advanced.DISPLAY_INDUSTRIES})
    di = advanced.diffusion_index(obs, window_months=6)
    disp = advanced.state_ur_dispersion(obs)
    edu_gap = prepare.education_gradient(obs)
    bev = advanced.beveridge_series(obs)
    occ = prepare.occupation_exposure(obs, meta, occ_exp)
    k = prepare.national_kpis(obs)

    kpis = {"Unemployment rate": _fmt(k["unemployment_rate"], "%"),
            "Participation": _fmt(k["lfpr"], "%"),
            "Bachelor's+ UR": _fmt(k["ur_bachelors"], "%"),
            "Job openings": _fmt(k["openings"], "k", 0),
            "Quits rate": _fmt(k["quits_rate"], "%")}
    kpi_html = "".join(
        f'<div class="kpi{" flag" if lab == "Bachelor\'s+ UR" else ""}">'
        f'<span class="v">{val}</span><span class="l">{lab}</span></div>'
        for lab, val in kpis.items())

    exposed_ids = [s for s, _, n in advanced.DISPLAY_INDUSTRIES if n in advanced._AI_NAICS]
    other_ids = [s for s, _, n in advanced.LEAF_PARTITION if n not in advanced._AI_NAICS]
    cd = advanced.change_distribution(obs, exposed_ids, other_ids, "2023-01", 12)

    # (id, title, caption, body, interactive)
    specs = [
        ("waterfall", "Where the jobs went",
         "Every dollar of net job growth, decomposed. Each industry's signed contribution to the "
         "total change between your two dates, summing to the net. Services build the total; "
         "Information drains it. <b>Recomputes as you change the dates above.</b>",
         '<div class="chart" id="c-waterfall" style="min-height:560px"></div>', True),
        ("distribution", "The distribution of industry change (beeswarm)",
         "One dot per <b>detailed (4-digit NAICS) industry</b>, around 180 of them, packed by its "
         "employment change and colored by AI exposure (clay = more exposed), sized by employment. "
         "At this density the beeswarm reveals the whole shape: a long clay (high-exposure) left "
         "tail against a slate body. <b>Recomputes with the dates.</b>",
         '<div class="chart" id="c-dist" style="min-height:580px"></div>', True),
        ("histogram", "How the distribution of change shifted",
         "A true histogram, because here the sample is large: every industry's 12-month employment "
         "change, every month since ChatGPT, pooled. AI-exposed industries (clay) sit a full "
         "distribution to the left of the rest (slate); dashed lines mark the medians.",
         _fig_html(charts_advanced.fig_change_histogram(cd), "c-hist"), False),
        ("scatter", "Does AI exposure predict job loss?",
         "The thesis on trial: each industry's AI-exposure score (AIIE) against its employment "
         "change, with a fitted line. A downward slope is the displacement signature, but watch the "
         "R-squared: exposure is <b>potential, not adoption</b>. <b>Recomputes with the dates.</b>",
         '<div class="chart" id="c-scatter" style="min-height:480px"></div>', True),
        ("event", "Information versus a control, around ChatGPT",
         "Information employment and a control (total private excluding Information), each indexed "
         "to 100 at the ChatGPT launch. If the lines track before the anchor and split after, that "
         "supports an AI break; pre-existing divergence would point to the tech-hiring unwind and "
         "rate hikes instead.",
         _fig_html(charts_advanced.fig_event_study(es), "c-event"), False),
        ("freeze", "Hiring freeze, or active cuts?",
         "Each JOLTS industry by its change in job openings (horizontal) against its change in "
         "layoffs (vertical). Bottom-left is a quiet freeze; top-left is active cutting. Information "
         "sits high-left: openings gone and layoffs up. <b>Recomputes with the dates.</b>",
         '<div class="chart" id="c-freeze" style="min-height:480px"></div>', True),
        ("breadth", "A decade of industry change, and its breadth",
         "Top: year-over-year employment change by industry, years as rows and industries as narrow "
         "columns (clay = shrinking, teal = growing); the information columns redden after 2022. "
         "Bottom: the share of industries growing, a breadth gauge. Payrolls can rise while breadth narrows.",
         _fig_html(charts_advanced.fig_industry_heatmap(matrix), "c-heatmap")
         + _fig_html(charts_advanced.fig_diffusion(di), "c-diffusion"), False),
        ("dispersion", "How unevenly slack is spread across states",
         "The middle bands hold the central 50% and 80% of states; the clay line is labor-force-"
         "weighted dispersion. A widening spread means states are diverging, which is what a "
         "geographically concentrated (tech-led) shock would produce.",
         _fig_html(charts_advanced.fig_dispersion_fan(disp), "c-dispersion"), False),
        ("states", "Every state, by unemployment change and tech intensity (beeswarm)",
         "One dot per state, packed by its change in unemployment, colored by its tech-employment "
         "share (Information plus professional services). If AI were the driver, the clay (tech-"
         "heavy) states would cluster on the right. They lean that way, but only weakly. "
         "<b>Recomputes with the dates.</b>",
         '<div class="chart" id="c-states" style="min-height:420px"></div>', True),
        ("education", "The education shield, tested",
         "The high-school-minus-bachelor's unemployment gap. Generative AI uniquely targets "
         "cognitive, degreed work, so a narrowing gap is the fingerprint to watch. It narrowed, but "
         "graduates still hold the lower rate, counter-evidence worth stating.",
         _fig_html(charts_advanced.fig_education_gap(edu_gap), "c-edugap"), False),
        ("beveridge", "The Beveridge curve: a round trip to balance",
         "Job-openings rate against unemployment, traced through time (color = year). The loop up "
         "and left in 2021 to 2022 was an overheated market; the return toward the origin is the "
         "normalization. This is macro context, not an AI-specific signal.",
         _fig_html(charts_advanced.fig_beveridge(bev), "c-beveridge"), False),
        ("occupations", "The stakes: exposed occupations today",
         "A 2025 snapshot (no time trend): each occupation by employment and LLM exposure, sized by "
         "headcount. It maps where exposed workers are, not whether they have been displaced. "
         "Exposure does not equal displacement.",
         _fig_html(charts.fig_occupation(occ), "c-occ"), False),
    ]
    ex = [_exhibit(n, sid, title, cap, body, inter)
          for n, (sid, title, cap, body, inter) in enumerate(specs, 1)]

    nav = "".join(f'<a href="#{s}">{t}</a>' for s, t in [
        ("findings", "Findings"), ("waterfall", "Where jobs went"),
        ("distribution", "Swarm"), ("histogram", "Histogram"), ("scatter", "Exposure test"),
        ("event", "Event study"), ("freeze", "Freeze vs cuts"), ("breadth", "Breadth"),
        ("dispersion", "State spread"), ("states", "State swarm"), ("education", "Education"),
        ("beveridge", "Beveridge"), ("occupations", "Stakes")])

    js = (_interactive_js().replace("__DATA__", data_json).replace("__MONTHS__", months_json)
          .replace("__BASE__", base_default).replace("__COMPARE__", compare_default))

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Has AI taken a toll on jobs? An interactive view</title>
<script src="{PLOTLY_CDN}" charset="utf-8"></script>
<style>{_css()}{_CONTROL_CSS}</style>
<script>document.documentElement.classList.add('js');</script>
</head><body>
<div class="toolbar"><div class="wrap">
  <span class="brand">AI &amp; US jobs</span>
  <input id="bls-key" type="password" autocomplete="off" placeholder="BLS API key (optional; uses .env default)">
  <button id="btn-refresh" class="primary" title="Re-fetch the latest data from the BLS API">&#x21bb; Refresh from BLS</button>
  <button id="btn-pdf" title="Open the browser print dialog; choose Save as PDF">&#x2913; PDF</button>
  <button id="btn-xlsx" title="Download every chart's data, one sheet per chart">&#x2913; Data (Excel)</button>
</div></div>
<div id="overlay"><div class="loader">
  <div class="bars"><i></i><i></i><i></i><i></i><i></i></div>
  <div class="msg">Fetching the latest data from BLS&hellip;</div>
  <div class="sub">This can take up to a minute. The page will reload when done.</div>
</div></div>
<header class="hero"><div class="wrap">
  <p class="kicker">US labor market, an interactive BLS data view</p>
  <h1>Has AI taken a toll on jobs?</h1>
  <p class="lede">Nine hundred BLS series, explorable. Pick any two dates and the decompositions,
  distributions, and relationships below all recompute. Data through {asof}.</p>
</div></header>
<div class="wrap"><div class="kpis">{kpi_html}</div></div>
<div class="controlbar"><div class="wrap">
  <span class="lab">Compare</span>
  <label>from <select id="sel-base"></select></label>
  <label>to <select id="sel-compare"></select></label>
  <span class="chips">
    <button class="preset" data-b="2019-12">vs 2019</button>
    <button class="preset" data-b="2022-11">vs ChatGPT</button>
    <button class="preset" data-b="2023-03">vs GPT-4</button>
  </span>
  <span class="readout" id="readout"></span>
</div></div>
<nav class="toc"><div class="wrap">{nav}</div></nav>
{_findings_html()}
{''.join(ex)}
<footer><div class="wrap">
  <div class="disclaimer"><b>Read with care.</b> These exhibits show correlation and timing, not
  causation. The 2022 to 2023 window also holds the post-pandemic tech-hiring unwind and the Fed's
  rate-hike cycle, both of which move these series. Treat the patterns as hypotheses to test.</div>
  <p class="note"><b>Sources.</b> Bureau of Labor Statistics (CPS, LAUS, CES, JOLTS, OEWS).
  AI-exposure: Eloundou, Manning, Mishkin and Rock (2023), GPTs are GPTs; Felten, Raj and Seamans,
  AI Occupational and Industry Exposure. As of {asof}.</p>
</div></footer>
<script>{js}</script>
<script>const io=new IntersectionObserver((es)=>es.forEach(e=>{{if(e.isIntersecting){{e.target.classList.add('in');io.unobserve(e.target)}}}}),{{threshold:0.06}});const fades=document.querySelectorAll('.fade');fades.forEach(el=>io.observe(el));setTimeout(()=>fades.forEach(el=>el.classList.add('in')),2500);</script>
<script>{_toolbar_js()}</script>
</body></html>"""

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _interactive_js() -> str:
    return r"""
const DATA = __DATA__;
const MONTHS = __MONTHS__;
const INK="#26272e", MUTED="#8a8d99", LINE="#e9e9ee", CLAY="#c2613a", SLATE="#5b6b8c", TEAL="#3a78b5";
const FONT="Inter,'Segoe UI',system-ui,sans-serif";
const CFG={displaylogo:false, responsive:true};

function lastOnOrBefore(dates, values, target){
  let v=null; for(let i=0;i<dates.length;i++){ if(dates[i]<=target && values[i]!=null) v=values[i]; } return v;
}
function chg(s, B, C){ const b=lastOnOrBefore(s.dates,s.values,B), c=lastOnOrBefore(s.dates,s.values,C);
  return (b==null||b===0||c==null)?null:(c/b-1)*100; }
function lvl(s, B, C){ const b=lastOnOrBefore(s.dates,s.values,B), c=lastOnOrBefore(s.dates,s.values,C);
  return (b==null||c==null)?null:(c-b); }
function tpl(extra){ return Object.assign({template:"plotly_white",paper_bgcolor:"rgba(0,0,0,0)",
  plot_bgcolor:"rgba(0,0,0,0)",font:{family:FONT,size:13,color:INK},margin:{l:60,r:24,t:16,b:46},
  xaxis:{gridcolor:LINE,zeroline:false,linecolor:LINE},yaxis:{gridcolor:LINE,zeroline:false,linecolor:"rgba(0,0,0,0)"},
  hoverlabel:{bgcolor:"#ffffff",bordercolor:LINE,font:{family:FONT,color:INK}}}, extra||{}); }
function diverge(v){ // aiie ~ [-1,2] -> color
  const t=Math.max(0,Math.min(1,(v+1)/3)); const r=Math.round(91+(194-91)*t), g=Math.round(107+(97-107)*t), b=Math.round(140+(58-140)*t);
  return `rgb(${r},${g},${b})`; }
function techColor(s){ const t=Math.max(0,Math.min(1,(s||0)/22)); // 0-22% tech share
  const r=Math.round(91+(194-91)*t), g=Math.round(107+(97-107)*t), b=Math.round(140+(58-140)*t); return `rgb(${r},${g},${b})`; }
function beeswarmY(xs){ // symmetric column-packed offsets so dots don't overlap
  const n=xs.length; if(!n) return []; const order=[...xs.keys()].sort((a,b)=>xs[a]-xs[b]);
  const lo=Math.min(...xs), hi=Math.max(...xs); const span=(hi-lo)||1; const binw=span/26;
  const y=new Array(n).fill(0); const bins={};
  for(const i of order){ const k=Math.round((xs[i]-lo)/binw); bins[k]=bins[k]||0;
    const idx=bins[k]++; y[i]=(idx%2===0?1:-1)*Math.ceil((idx+1)/2); }
  const maxAbs=Math.max(1,...y.map(Math.abs)); return y.map(v=>v/maxAbs); // normalize to [-1,1]
}

function drawWaterfall(B,C){
  const rows=DATA.industries.filter(d=>d.leaf).map(d=>({label:d.label, v:lvl(d,B,C)})).filter(r=>r.v!=null)
    .sort((a,b)=>b.v-a.v);
  const net=rows.reduce((a,r)=>a+r.v,0);
  const x=rows.map(r=>r.v).concat([net]); const y=rows.map(r=>r.label).concat(["Net change"]);
  const measure=rows.map(()=>"relative").concat(["total"]);
  Plotly.react("c-waterfall",[{type:"waterfall",orientation:"h",measure:measure,x:x,y:y,
    decreasing:{marker:{color:CLAY}},increasing:{marker:{color:TEAL}},totals:{marker:{color:INK}},
    connector:{line:{color:LINE}},hovertemplate:"%{y}: %{x:+,.0f}k<extra></extra>"}],
    tpl({height:Math.max(560,30*y.length+90),xaxis:{title:"Contribution to net job change (000s)",
      gridcolor:LINE,zeroline:true,zerolinecolor:MUTED},yaxis:{automargin:true,autorange:"reversed"}}),CFG);
}
function drawDistribution(B,C){
  const src=(DATA.detailed&&DATA.detailed.length)?DATA.detailed:DATA.industries.filter(d=>d.display);
  const pts=src.map(d=>({label:d.label,x:chg(d,B,C),aiie:d.aiie,emp:d.values.slice(-1)[0]}))
    .filter(p=>p.x!=null && p.x>-60 && p.x<80);
  const ys=beeswarmY(pts.map(p=>p.x));
  Plotly.react("c-dist",[
    {type:"box",x:pts.map(p=>p.x),name:"",orientation:"h",boxpoints:false,marker:{color:SLATE},
      line:{color:SLATE,width:1},fillcolor:"rgba(91,107,140,0.06)",y0:0,hoverinfo:"skip",showlegend:false},
    {type:"scatter",mode:"markers",x:pts.map(p=>p.x),y:ys,
      marker:{size:pts.map(p=>Math.max(6,Math.min(20,Math.sqrt(p.emp||1)/14))),
        opacity:0.82,line:{color:"#ffffff",width:0.5},
        color:pts.map(p=>p.aiie==null?0:p.aiie),colorscale:[[0,TEAL],[0.5,"#cfd6dd"],[1,CLAY]],cmin:-1,cmax:2,
        showscale:true,colorbar:{title:"AI exp",thickness:11,len:0.5,outlinewidth:0}},
      text:pts.map(p=>p.label),customdata:pts.map(p=>p.aiie==null?"n/a":p.aiie.toFixed(2)),
      hovertemplate:"%{text}<br>change %{x:+.1f}%<br>AI exposure %{customdata}<extra></extra>",showlegend:false}],
    tpl({height:560,margin:{l:24,r:24,t:16,b:46},
      xaxis:{title:"Employment change (%), "+pts.length+" industries",ticksuffix:"%",gridcolor:LINE,zeroline:true,zerolinecolor:MUTED},
      yaxis:{visible:false,range:[-1.15,1.15]}}),CFG);
}
function drawStatesSwarm(B,C){
  const pts=(DATA.states||[]).map(s=>({abbr:s.abbr,x:lvl(s,B,C),tech:s.tech})).filter(p=>p.x!=null);
  const ys=beeswarmY(pts.map(p=>p.x));
  Plotly.react("c-states",[{type:"scatter",mode:"markers+text",x:pts.map(p=>p.x),y:ys,
    text:pts.map(p=>p.abbr),textposition:"top center",textfont:{size:9,color:MUTED},
    marker:{size:15,opacity:0.9,line:{color:"#ffffff",width:1},
      color:pts.map(p=>p.tech==null?0:p.tech),colorscale:[[0,"#5b6b8c"],[1,CLAY]],
      cmin:0,cmax:22,showscale:true,colorbar:{title:"tech %",thickness:12,len:0.6,outlinewidth:0}},
    customdata:pts.map(p=>p.tech==null?"n/a":p.tech.toFixed(1)),
    hovertemplate:"%{text}<br>UR change %{x:+.1f} pp<br>tech share %{customdata}%<extra></extra>",showlegend:false}],
    tpl({height:420,xaxis:{title:"Change in unemployment rate (pp)",ticksuffix:" pp",gridcolor:LINE,zeroline:true,zerolinecolor:MUTED},
      yaxis:{visible:false,range:[-1.6,1.6]}}),CFG);
}
function ols(xs,ys){ const n=xs.length; if(n<2) return null; let sx=0,sy=0,sxx=0,sxy=0,syy=0;
  for(let i=0;i<n;i++){sx+=xs[i];sy+=ys[i];sxx+=xs[i]*xs[i];sxy+=xs[i]*ys[i];syy+=ys[i]*ys[i];}
  const d=n*sxx-sx*sx; if(d===0) return null; const m=(n*sxy-sx*sy)/d, b=(sy-m*sx)/n;
  const r=(n*sxy-sx*sy)/Math.sqrt(Math.max(1e-9,(n*sxx-sx*sx)*(n*syy-sy*sy))); return {m,b,r2:r*r}; }
function drawScatter(B,C){
  const pts=DATA.industries.filter(d=>d.display&&d.aiie!=null).map(d=>({label:d.label,x:d.aiie,y:chg(d,B,C),emp:d.values.slice(-1)[0]}))
    .filter(p=>p.y!=null);
  const fit=ols(pts.map(p=>p.x),pts.map(p=>p.y));
  const traces=[{type:"scatter",mode:"markers+text",x:pts.map(p=>p.x),y:pts.map(p=>p.y),
    text:pts.map(p=>p.label),textposition:"top center",textfont:{size:9,color:MUTED},
    marker:{size:pts.map(p=>Math.max(9,Math.sqrt(p.emp||1)/12)),color:pts.map(p=>p.y<0?CLAY:TEAL),opacity:0.85,line:{color:"#ffffff",width:1}},
    hovertemplate:"%{text}<br>AI exposure %{x:.2f}<br>change %{y:+.1f}%<extra></extra>",showlegend:false}];
  let ann=[];
  if(fit){ const xs=pts.map(p=>p.x); const xmin=Math.min(...xs),xmax=Math.max(...xs);
    traces.push({type:"scatter",mode:"lines",x:[xmin,xmax],y:[fit.m*xmin+fit.b,fit.m*xmax+fit.b],
      line:{color:INK,width:1.5,dash:"dash"},hoverinfo:"skip",showlegend:false});
    ann=[{xref:"paper",yref:"paper",x:0.98,y:0.04,xanchor:"right",showarrow:false,
      text:`slope ${fit.m.toFixed(1)} pp per exposure unit, R&sup2; ${fit.r2.toFixed(2)} (weak)`,
      font:{color:MUTED,size:12}}]; }
  Plotly.react("c-scatter",traces,tpl({height:480,annotations:ann,
    xaxis:{title:"AI industry exposure (AIIE)",gridcolor:LINE,zeroline:true,zerolinecolor:MUTED},
    yaxis:{title:"Employment change (%)",ticksuffix:"%",gridcolor:LINE,zeroline:true,zerolinecolor:MUTED}}),CFG);
}
function drawFreeze(B,C){
  const op={},ld={}; DATA.jolts.forEach(s=>{const m=s.element==="openings"?op:ld; m[s.code]={s:s,label:s.label};});
  const pts=[]; Object.keys(op).forEach(code=>{ if(!(code in ld)) return;
    const x=chg(op[code].s,B,C), y=chg(ld[code].s,B,C); if(x==null||y==null) return;
    pts.push({label:op[code].label,x:x,y:y,emp:op[code].s.values.slice(-1)[0]}); });
  Plotly.react("c-freeze",[{type:"scatter",mode:"markers+text",x:pts.map(p=>p.x),y:pts.map(p=>p.y),
    text:pts.map(p=>p.label),textposition:"top center",textfont:{size:10,color:INK},
    marker:{size:14,color:pts.map(p=>(p.x<0&&p.y>0)?CLAY:(p.x>0?TEAL:SLATE)),opacity:0.85,line:{color:"#ffffff",width:1}},
    hovertemplate:"%{text}<br>openings %{x:+.0f}%<br>layoffs %{y:+.0f}%<extra></extra>",showlegend:false}],
    tpl({height:480,xaxis:{title:"Job-openings change (%)",ticksuffix:"%",gridcolor:LINE,zeroline:true,zerolinecolor:MUTED},
      yaxis:{title:"Layoffs change (%)",ticksuffix:"%",gridcolor:LINE,zeroline:true,zerolinecolor:MUTED},
      annotations:[{x:0.02,y:0.98,xref:"paper",yref:"paper",text:"active cuts",showarrow:false,font:{color:CLAY,size:11}},
        {x:0.02,y:0.02,xref:"paper",yref:"paper",text:"quiet freeze",showarrow:false,font:{color:MUTED,size:11}}]}),CFG);
}
function fmtMonth(m){const [y,mo]=m.split("-");return new Date(y,mo-1,1).toLocaleString("en",{month:"short",year:"numeric"});}
function updateAll(){
  const B=document.getElementById("sel-base").value, C=document.getElementById("sel-compare").value;
  drawWaterfall(B,C); drawDistribution(B,C); drawScatter(B,C); drawFreeze(B,C); drawStatesSwarm(B,C);
  const info=DATA.sectors.find(s=>s.label==="Information"); const ic=info?chg(info,B,C):null;
  document.getElementById("readout").innerHTML="Information payrolls <b>"+(ic==null?"n/a":(ic>=0?"+":"")+ic.toFixed(1)+"%</b>")+" from "+fmtMonth(B)+" to "+fmtMonth(C);
}
(function init(){
  const sb=document.getElementById("sel-base"), sc=document.getElementById("sel-compare");
  MONTHS.forEach(m=>{ sb.add(new Option(fmtMonth(m),m)); sc.add(new Option(fmtMonth(m),m)); });
  sb.value="__BASE__"; sc.value="__COMPARE__";
  sb.addEventListener("change",updateAll); sc.addEventListener("change",updateAll);
  document.querySelectorAll(".preset").forEach(btn=>btn.addEventListener("click",()=>{
    if(MONTHS.includes(btn.dataset.b)){ sb.value=btn.dataset.b; updateAll(); }}));
  updateAll();
})();
"""


def _toolbar_js() -> str:
    return r"""
const $=id=>document.getElementById(id);
const served=()=>location.protocol.indexOf("http")===0;
function overlay(on){ $("overlay").classList.toggle("show", on); }
async function doRefresh(force){
  const key=$("bls-key").value.trim();
  overlay(true);
  try{
    const r=await fetch("/api/refresh",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({key:key||null, force:!!force})});
    const d=await r.json();
    if(d.ok){ location.reload(); return; }
    overlay(false);
    if(d.warning){ if(confirm(d.warning)) doRefresh(true); }
    else alert(d.error || "Refresh failed.");
  }catch(e){ overlay(false);
    alert("Refresh needs the local app. Run:  python app.py  then open http://127.0.0.1:8765"); }
}
$("btn-refresh").addEventListener("click", async ()=>{
  if(!served()){ alert("Open via the local app (python app.py) to refresh from BLS."); return; }
  try{ const s=await (await fetch("/api/status")).json();
    if(s.fresh && !confirm("Data was refreshed "+s.age_hours+"h ago. BLS updates these series monthly, "+
      "so refreshing now will usually return the same numbers and just spends API quota. Refresh anyway?")) return;
  }catch(e){}
  doRefresh(false);
});
$("btn-pdf").addEventListener("click", ()=>window.print());
$("btn-xlsx").addEventListener("click", ()=>{
  if(!served()){ alert("Open via the local app (python app.py) to export the Excel workbook."); return; }
  const B=$("sel-base").value, C=$("sel-compare").value;
  window.location="/api/export/data.xlsx?base="+B+"&compare="+C;
});
"""
