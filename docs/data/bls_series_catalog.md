# BLS Series Catalog — Comprehensive Unemployment & Workforce Tracking

**Purpose:** Master catalog of BLS data series for a granular US unemployment/workforce report, instrumented to test *whether AI has taken a toll on jobs*. Dimensions covered: national headline, **states/metros/counties**, **occupation/profession**, **educational attainment**, **industry**, and **labor-demand flows (job openings, hires, quits, layoffs)**.

**Status:** Series-gathering phase only (per request). No pipeline built yet. Downstream build target = interactive HTML/Plotly report + descriptive AI-impact analysis (econometric layer later).

> **Verification note:** Every series ID below was verified live against the BLS Public Data API v2 (`https://api.bls.gov/publicAPI/v2/timeseries/data/`) or authoritative BLS flat files, except where flagged. The `bls.gov` HTML site and `download.bls.gov` flat-file host are Akamai bot-protected (return HTTP 403 to scripted fetches) — **the JSON API is the reliable programmatic source**, not the website.

---

## 0. BLS API — access, your key, limits

### Your registration key — where it is
- The BLS API key is **emailed to you immediately on registration** at **https://data.bls.gov/registrationEngine/**. It is a 32-character hex string.
- **There is no account dashboard or "my keys" page** on BLS — you cannot look it up after the fact. It lives only in that registration email.
- **To find it:** search your inbox (and spam) for sender `@bls.gov`, subject ~ *"BLS Public Data API Registration"* / *"...Registration Key"*, sent to the email you registered with.
- **If lost:** simply **re-register at the same portal with the same email** — you get a fresh key in seconds. (Old keys generally keep working; re-registering is the fastest recovery since BLS offers no resend UI.)
- Store it as env var `BLS_API_KEY` for the future pipeline. Never hard-code it.

### v2 (registered) vs v1 (keyless) limits
| | **v2 (with key)** | v1 (no key) |
|---|---|---|
| Daily queries | 500 | 25 |
| Series per request | 50 | 25 |
| Years per request | 20 | 10 |
| Net/percent change calcs | Yes | No |
| Series catalog/metadata | Yes | No |
| Endpoint | `…/publicAPI/v2/timeseries/data/` | `…/publicAPI/v1/...` |

**Implication for this project:** with the key, the full granular pull (all states, AI-exposed industries/occupations, JOLTS, education cuts, 20yr history) fits comfortably — batch ≤50 series/request, ≤500 requests/day. Keyless is too tight for this scope.

### Query shape (POST JSON)
```
POST https://api.bls.gov/publicAPI/v2/timeseries/data/
{
  "seriesid": ["LNS14000000", "JTS000000000000000JOL", ...],   // ≤50
  "startyear": "2005", "endyear": "2026",                       // ≤20yr span
  "registrationkey": "<BLS_API_KEY>",
  "calculations": true, "annualaverage": true, "catalog": true
}
```

Sources: [Getting Started](https://www.bls.gov/developers/home.htm) · [API Signatures v2](https://www.bls.gov/developers/api_signature_v2.htm) · [API FAQs](https://www.bls.gov/developers/api_faqs.htm) · [Registration portal](https://data.bls.gov/registrationEngine/)

---

## Coverage map (which program answers which question)

| Your ask | Program | Prefix | Granularity | Frequency |
|---|---|---|---|---|
| Unemployment rate, labor force, U-1–U-6, by **education**, demographics, duration | CPS | `LN` | National, monthly | Monthly |
| Unemployment by **state / metro / county / city** | LAUS | `LA` | 50 states+DC+PR, ~7,500 areas | Monthly |
| **Employment / payrolls** by industry & by state/metro; hours; earnings | CES / SAE | `CE`, `SM` | National + state/metro × NAICS | Monthly |
| **Job openings, hires, quits, layoffs** | JOLTS | `JT` | National + 4 census regions × industry | Monthly (~1mo lag) |
| Employment & wages by **occupation (profession)** | OEWS | `OE` | National/state/metro × 6-digit SOC | Annual snapshot |
| 10-yr **occupation outlook** (automation-aware) | Employment Projections | `EP` | Occupation × industry | Annual (flat files) |
| **AI exposure** scores to join to the above | External | — | SOC / NAICS / O*NET / FIPS | One-off datasets |

---

## CPS — National Labor Force (LN series)

The national labor force statistics from the Current Population Survey (CPS, a ~60,000-household monthly survey conducted by the Census Bureau for BLS) are distributed through the BLS **LN** database. Data cover the civilian noninstitutional population aged 16+, reference the calendar week containing the 12th of the month, and are released with the monthly *Employment Situation*. IDs verified against the `ln.series` flat file and live API/FRED.

### Series ID anatomy

The LN series ID has only **three decodable components**; the remaining digits are an internal catalog code and are **NOT positionally decodable** (unlike CES/CPI). To map a code to a concept, consult `ln.series`.

| Field | Positions | Length | Values / Example |
|---|---|---|---|
| `prefix` | 1–2 | 2 | `LN` (Labor force statistics, CPS) |
| `seasonal` | 3 | 1 | `S` = Seasonally Adjusted; `U` = Not Seasonally Adjusted |
| `series_code` | 4–11 | 8 | e.g. `14000000` (opaque catalog code) |

- **`LNS…` = SA**, **`LNU…` = NSA**. Example: `LNS14000000` (SA UR) vs `LNU04000000` (NSA UR).
- Trailing **`Q`** = quarterly-average version (e.g. `LNS14000000Q`). Annual averages appear as period `M13` within the monthly series.
- **Critical caveat:** SA and NSA IDs for the same concept are usually NOT identical except for char 3. SA headline measures use `LNS1X……`; the NSA twin uses `LNU0X……` with *different* trailing digits. **Never assume you can flip `S`↔`U` and keep the rest constant — look the NSA twin up.**
- Mapping files in `download.bls.gov/pub/time.series/ln/`: `ln.ages`, `ln.education`, `ln.occupation`, `ln.indy`, `ln.race`, `ln.orig`, `ln.sexs`, `ln.duration`, `ln.lfst`.

### 1. Headline series (monthly; SA from 1948, NSA from 1947)

| Measure | SA | NSA |
|---|---|---|
| Civilian Unemployment Rate (16+, U-3) | `LNS14000000` | `LNU04000000` |
| Civilian Labor Force Level | `LNS11000000` | `LNU01000000` |
| Employment Level | `LNS12000000` | `LNU02000000` |
| Unemployment Level | `LNS13000000` | `LNU03000000` |
| Labor Force Participation Rate | `LNS11300000` | `LNU01300000` |
| Employment-Population Ratio | `LNS12300000` | `LNU02300000` |

> The headline UR is `LNS14000000`, **not** `…04000000` (common error).

### 2. Alternative measures of labor underutilization (U-1–U-6)

U-1/2/3 from 1948–1967; U-4–U-6 from **1994**.

| Measure | SA | NSA |
|---|---|---|
| U-1 (unemployed ≥15 wks, % of LF) | `LNS13025670` | `LNU03025670` |
| U-2 (job losers + completed temp, % of LF) | `LNS14023621` | `LNU04023621` |
| U-3 (official rate) | `LNS14000000` | `LNU04000000` |
| U-4 (+ discouraged) | `LNS13327707` | `LNU03327707` |
| U-5 (+ all marginally attached) | `LNS13327708` | `LNU03327708` |
| U-6 (+ marginally attached + PTER) | `LNS13327709` | `LNU03327709` |

### 3. Unemployment rate by educational attainment, 25 yrs & over ⭐ (critical AI cut)

Monthly; history from **1992**; SA and NSA both published.

| Attainment | SA | NSA |
|---|---|---|
| Less than a high school diploma | `LNS14027659` | `LNU04027659` |
| High school graduates, no college | `LNS14027660` | `LNU04027660` |
| Some college or associate degree | `LNS14027689` | `LNU04027689` |
| Bachelor's degree and higher | `LNS14027662` | `LNU04027662` |

> Caution: NSA `LNU04027661` is the narrower "Some college, **no degree**". Use `…27689` for "some college **or associate degree**". Source table: A-4. Companion LFPR/emp-pop by education exist as `LNS113…`/`LNS123…` variants.

### 4. By demographics (representative SA; NSA twins use `LNU04…`)

- **Age:** 16–19 `LNS14000012`; 20+ `LNS14000024`; 25–54 (prime) `LNS14000060`; 55+ `LNS14024230`; 25–34 `LNS14000089`; 35–44 `LNS14000091`; 45–54 `LNS14000093`.
- **Sex (20+):** Men `LNS14000025`; Women `LNS14000026`.
- **Race/ethnicity:** White `LNS14000003`; Black `LNS14000006`; Hispanic `LNS14000009`; Asian `LNS14032183` (SA from 2003). Hispanic origin is tracked separately from race and can overlap.

### 5. Unemployment by occupation (A-30) and industry (A-14) — NSA only, from 2000

Classified by the person's **last job held**.
- **By occupation (A-30):** e.g. Natural Resources/Construction/Maintenance `LNU04032222`; Construction & Extraction `LNU04032224`. Major + detailed cuts keyed by `occupation_code` (`ln.occupation`).
- **By industry (A-14):** e.g. Construction private wage & salary `LNU04032231`; Manufacturing `LNU04032232`. Keyed by `indy_code` (`ln.indy`).
- **To enumerate:** filter `ln.series` for `seasonal=U`, `lfst_code=40` (rate) or `30` (level) with non-zero `occupation_code`/`indy_code`.

### 6. Duration, reason, PTER, marginal attachment, discouraged

| Concept | SA | NSA | Start |
|---|---|---|---|
| Mean weeks unemployed | `LNS13008275` | `LNU03008275` | 1948 |
| Median weeks unemployed | `LNS13008276` | `LNU03008276` | 1967 |
| Unemployed <5 wks (level) | `LNS13008396` | `LNU03008396` | 1948 |
| Unemployed 15+ wks (level) | `LNS13008516` | `LNU03008516` | 1948 |
| Unemployed 27+ wks (level) | `LNS13008636` | `LNU03008636` | 1948 |
| % of LF unemployed 27+ wks | `LNS13092836` | `LNU03092836` | 2011 |
| Job losers (level) | `LNS13023621` | `LNU03023621` | 1967 |
| Job leavers (level) | `LNS13023705` | `LNU03023705` | 1967 |
| Reentrants (level) | `LNS13023557` | `LNU03023557` | 1967 |
| New entrants (level) | `LNS13023569` | `LNU03023569` | 1967 |
| Part-time for economic reasons (level) | `LNS12032194` | `LNU02032194` | 1955 |
| Marginally attached (level) | `LNS15026642` | `LNU05026642` | 1994 |
| Discouraged workers (level) | `LNS15026645` | `LNU05026645` | 1994 |

### Relevance to AI-impact tracking
- **Educational attainment (§3) is the single most useful national cut.** GenAI exposure concentrates in cognitive white-collar work, unlike prior automation. Watch whether **bachelor's+ (`LNS14027662`)** rises faster than **≤HS (`LNS14027659/60`)** — a compression/inversion of the usual "education protects" gradient is a leading structural signal. Pair UR with the LFPR/emp-pop-by-education variants to separate displacement from withdrawal. (1992 start; ~0.2–0.4pp subgroup noise → use 3-month averages.)
- **Occupation (§5, A-30)** is second-best but constrained: NSA-only, 2000 start, last-job basis, broad groups. Complement with OEWS + CPS employed-by-occupation.
- **Duration & reason (§6):** a structural AI shock should show rising mean/median **duration**, higher **27+ wk share**, and a mix shift toward **job losers** vs voluntary leavers — distinguishing permanent tech separations from cyclical churn.

Sources: [Series ID Formats](https://www.bls.gov/help/hlpforma.htm) · [ln.series](https://download.bls.gov/pub/time.series/ln/ln.series) · [CPS Tables](https://www.bls.gov/cps/tables.htm) · [A-30 occupation](https://www.bls.gov/web/empsit/cpseea30.htm) · [A-14 industry](https://www.bls.gov/news.release/empsit.t14.htm)

---

## LAUS — Local Area Unemployment Statistics (LA series)

Monthly model-based estimates of labor force, employment, unemployment, and the unemployment rate for ~7,500 areas: nation, 50 states + DC + PR, all MSAs/metro divisions/micropolitan/NECTAs, counties, and ~1,300 cities ≥25,000. All IDs verified live against the API.

### Series ID anatomy (fixed 20-char string)

`LA` + seasonal(1) + area code(15) + measure(2)

| Field | Positions | Width | Contents |
|---|---|---|---|
| Prefix | 1–2 | 2 | `LA` |
| Seasonal | 3 | 1 | `S` = SA, `U` = NSA |
| Area code | 4–18 | 15 | 2-char area-type + 13-char zero-padded area identifier |
| Measure | 19–20 | 2 | statistic (table below) |

Within the area code: area-type (2) + state FIPS (2) + specific geography (FIPS county / CBSA / FIPS place), zero-padded.

**Decode `LAUST060000000000003`:** `LA` · `U` (NSA) · `ST` (statewide) · `06` (California) · zeros · `03` (UR).

### Area-type codes
| Type | Code | SA available? |
|---|---|---|
| Statewide | `ST` | SA + NSA (SA from Jan 1976) |
| Metro statistical area | `MT` | NSA in `MT`; SA via separate smoothed-metro program |
| County / equivalent | `CN` | NSA only |
| City/town ≥25,000 | `CT` | NSA only |

### Measure codes (the only four LAUS publishes)
| Code | Statistic | Units |
|---|---|---|
| `03` | Unemployment rate | percent |
| `04` | Unemployment level | persons |
| `05` | Employment level | persons |
| `06` | Civilian labor force level | persons |

> LAUS does **not** publish emp-pop ratio or LFPR (those are CPS-only).

### Enumerate all states (424 statewide series)
Pattern: **`LA{S|U}ST{FIPS2}00000000000{MM}`**. Loop 53 FIPS (`01,02,04,05,06,…,56`, DC `11`, PR `72` — note gaps at 03/07/14/43/52) × {`S`,`U`} × {`03,04,05,06`}. Examples:
- `LASST060000000000003` — California, SA, UR ✓
- `LASST480000000000003` — Texas, SA, UR ✓
- `LASST360000000000003` — New York, SA, UR

### Metros (NSA; pattern `LAUMT{FIPS2}{CBSA5}000000{MM}`)
- `LAUMT063108000000003` — Los Angeles–Long Beach–Anaheim (CBSA 31080), UR ✓
- `LAUMT363562000000003` — New York–Newark–Jersey City (CBSA 35620), UR ✓
- `LAUMT171698000000003` — Chicago–Naperville–Elgin (CBSA 16980), UR ✓

### County / city (NSA)
- County (`CN`, 5-digit FIPS): `LAUCN060730000000003` — San Diego County ✓
- City (`CT`, 7-digit place): `LAUCT064400000000003` — Los Angeles city ✓

**SA for metros** is published via a separate **smoothed seasonally adjusted metro** product (from Jan 1990), not via an `S`-flag swap on `MT` (a direct `LASMT…` query fails). History: statewide from 1976; sub-state from 1990. Cadence: monthly (statewide ~3-wk lag; sub-state ~1 wk later). Annual benchmark revision each spring.

### Relevance to AI-impact tracking
AI/tech-exposed employment is **spatially concentrated** — a national rate masks metro divergence. Build a panel of UR + unemployment level for AI-dense metros — SF–Oakland (CBSA 41860), San Jose (41940), Seattle (42660), Austin (12420), NYC (35620), LA (31080) — and benchmark against parent-state `LASST` and national. Caveats: sub-state is **NSA** (compare YoY or use smoothed-SA file); LAUS is **residence-based** (where workers live), so pair with establishment-based CES for industry/occupation attribution; small-area estimates have wider SEs.

Sources: [Series ID Formats](https://www.bls.gov/help/hlpforma.htm) · [Extracting LAUS Data](https://www.bls.gov/lau/lausad.htm) · [Smoothed SA Metro](https://www.bls.gov/lau/metrossa.htm) · [LAUS Home](https://www.bls.gov/lau/)

---

## CES — Employment (National CE + State/Metro SM series)

The Current Employment Statistics establishment ("payroll") survey: ~119,000 businesses, source of the headline nonfarm payroll number — the labor-**demand** counterpart to household unemployment. Two API families: **CE** (national) and **SM** (state & metro / SAE). All IDs verified live.

### Series ID anatomy — National CE (13 chars)
`CE` + seasonal(1) + supersector+industry(8) + datatype(2)

| Positions | Field | Notes |
|---|---|---|
| 1–2 | Prefix | `CE` |
| 3 | Seasonal | `S` / `U` |
| 4–11 | Industry | 2-digit supersector + 6-digit NAICS detail; `00000000` = Total nonfarm |
| 12–13 | Data type | `01` = all employees, etc. |

Decode `CES0500000003`: `CE` · `S` · `05000000` (total private) · `03` (avg hourly earnings) → $37.02/hr.

### Supersector codes (first 2 digits of industry field)
| Code | Supersector |
|---|---|
| `00000000` | **Total nonfarm** |
| `05000000` | Total private |
| `06000000` | Goods-producing |
| `10000000` | Mining and logging |
| `20000000` | Construction |
| `30000000` | Manufacturing (`31`=durable, `32`=nondurable) |
| `40000000` | Trade, transportation & utilities (`41` wholesale, `42` retail, `43` transport/warehouse, `44` utilities) |
| **`50000000`** | **Information** ⭐ AI-exposed |
| `55000000` | Financial activities |
| **`60000000`** | **Professional & business services** ⭐ AI-exposed |
| `65000000` | Private education & health services |
| `70000000` | Leisure & hospitality |
| `80000000` | Other services |
| `90000000` | Government |

### Data type codes (verified)
| Code | Meaning |
|---|---|
| `01` | All employees, thousands |
| `02` | Avg weekly hours, all employees |
| `03` | Avg hourly earnings, all employees ($) |
| `11` | Avg weekly earnings, all employees ($) |
| `06` | Production/nonsupervisory employees, thousands |
| `07` / `08` / `30` | Prod. weekly hours / hourly earnings / weekly earnings |
| `10` | Women employees, thousands |
| `21`–`24` | 1/3/6/12-month diffusion indexes |

> Note: code `11` is weekly **earnings**, not weekly hours; all-employee weekly **hours** = `02`.

### Verified CE examples
| Series ID | Description |
|---|---|
| `CES0000000001` | Total nonfarm, all employees, SA (headline payrolls) |
| `CES5000000001` | **Information**, all employees, SA |
| `CES6000000001` | **Professional & business services**, all employees, SA |
| `CES0500000003` | Total private, avg hourly earnings, SA |
| `CES0500000002` | Total private, avg weekly hours, SA |

(NSA = replace `S` with `U`, e.g. `CEU0000000001`.)

### Series ID anatomy — State & Metro SM (20 chars)
`SM` + seasonal(1) + state FIPS(2) + area(5) + industry(8) + datatype(2)

- **States:** loop FIPS `01`–`56` (+ DC `11`, PR `72`, VI `78`), area `00000` = statewide.
- **Metros:** 5-digit BLS SAE area code (≈ but not identical to OMB CBSA) — e.g. `35620` NYC, `31080` LA, `16980` Chicago, `19100` Dallas, `26420` Houston. Probe API; treat "Series does not exist" as not-published.
- **SM data types:** `01` universal; `06`; hours/earnings (`02/03/07/08/11/30`) only for selected states/large metros.

Verified SM examples:
| Series ID | Decode |
|---|---|
| `SMS06000000000000001` | CA statewide, total nonfarm, all employees, SA |
| `SMS36356200000000001` | NY, NYC metro (35620), total nonfarm, SA |
| `SMS06000005000000001` | CA statewide, **Information**, SA |
| `SMS06000006000000001` | CA statewide, **Prof. & business services**, SA |

Cadence: monthly with Employment Situation (~1st Friday); SAE ~1 wk after national. Annual benchmark to QCEW each January; latest 2 months preliminary. History: national from 1939 (NAICS detail from 1990); SAE NAICS from 1990.

### Relevance to AI-impact tracking
**Information (`50`)** and **Professional & business services (`60`)** are the two most AI-exposed supersectors — track `CES5000000001` / `CES6000000001` and sub-industries for suppressed knowledge/clerical hiring; localize via SM in tech metros. **Hours and earnings are leading indicators:** firms cut **hours before headcount**, so avg weekly hours (`02`/`07`) soften ahead of payroll declines; earnings (`03`/`11`) capture wage cooling. Diffusion indexes (`21`–`24`) show how broadly weakness spreads.

Sources: live API v2 verification; [CES](https://www.bls.gov/ces/) · [SAE](https://www.bls.gov/sae/) · flat files `download.bls.gov/pub/time.series/ce/` and `/sm/`.

---

## JOLTS — Job Openings & Labor Turnover (JT series)

Monthly labor demand and turnover flows: job openings, hires, separations (quits, layoffs/discharges, other). Canonical source for openings-to-unemployed tightness and the quits rate. All IDs verified live (data through ~April 2026).

### Series ID anatomy (fixed 21-char string)
| Positions | Field | Notes |
|---|---|---|
| 1–2 | Prefix | `JT` |
| 3 | Seasonal | `S` / `U` |
| 4–9 | Industry | NAICS-based; `000000` = total nonfarm |
| 10–11 | State / region | `00` = national; regions `NE`/`SO`/`MW`/`WE` |
| 12–16 | Area | `00000` = all (MSA detail reserved) |
| 17–18 | Size class | `00` = all sizes |
| 19–20 | Data element | `JO`,`HI`,`TS`,`QU`,`LD`,`OS` |
| 21 | Rate/level | `L` = level (thousands), `R` = rate (%) |

Decode `JTS000000000000000JOL` = SA, total nonfarm, national, all areas, all sizes, **job openings, level**.

> Element is the **2** chars at 19–20; rate/level is the **1** char at 21. Don't mis-split as a 3-char `JOL` token.

### Data elements
| Code | Element | Forms |
|---|---|---|
| `JO` | Job openings | L, R |
| `HI` | **Hires** | L, R |
| `TS` | Total separations | L, R |
| `QU` | Quits | L, R |
| `LD` | Layoffs & discharges | L, R |
| `OS` | Other separations | L, R |

Identity: `TS = QU + LD + OS`. **Unemployed-per-opening ratio is NOT a JT series** — compute it: unemployed `LNS13000000` ÷ openings `JTS000000000000000JOL` (both in thousands). <1 = tight, >1 = slack.

### Industry codes (positions 4–9)
`000000` total nonfarm · `100000` total private · `110099` mining/logging · `230000` construction · `300000` manufacturing (`320000` durable, `340000` nondurable) · `400000` trade/transport/utilities · **`510000` Information** ⭐ · **`540099` Professional & business services** ⭐ · `600000` private ed & health · `700000` leisure/hospitality · `900000` government.

> PBS uses non-round `540099` (not `540000`). Sub-industry detail: `download.bls.gov/pub/time.series/jt/jt.industry`.

### Regions (positions 10–11): `NE` Northeast, `SO` South, `MW` Midwest, `WE` West (regions ≈ sum to national). State-level JOLTS is **experimental** (separate product, not standard API series).

### Verified examples
| Series ID | Description |
|---|---|
| `JTS000000000000000JOL` | Total nonfarm, job openings, level, SA |
| `JTS000000000000000HIL` | Total nonfarm, **hires, level**, SA |
| `JTS000000000000000HIR` | Total nonfarm, hires, rate, SA |
| `JTS000000000000000QUR` | Total nonfarm, quits, rate, SA |
| `JTS510000000000000JOL` | **Information**, openings, level, SA |
| `JTS540099000000000HIL` | **Prof. & business services**, hires, level, SA |
| `JTU000000000000000JOL` | Total nonfarm, openings, level, **NSA** |

Cadence: monthly, but **~1 month behind the jobs report** (confirming, slightly stale read). History: NAICS-based from **Dec 2000**. Latest month preliminary; annual benchmark.

### Relevance to AI-impact tracking
- **Falling openings in AI-exposed industries** (`JTS510000…JOL`, `JTS540099…JOL`) are a **forward-looking** demand signal that precedes CES payroll losses — track vs total nonfarm to separate AI-concentrated softening from broad cyclicality.
- **Hiring slowdown ≠ layoffs:** AI displacement may show as a **hiring freeze** (falling `HIL`/`HIR`, stable `LD`) — a "low-hire, low-fire" market — rather than a layoff spike. Watch hires and layoffs together by industry.
- **Quits (`QUR`)** proxy worker confidence/outside options; declining quits in exposed sectors signal eroding bargaining power.

Sources: [Series ID Formats](https://www.bls.gov/help/hlpforma.htm) · [JOLTS Series Code Changes](https://www.bls.gov/jlt/jlt_series_changes.htm) · [jt.industry](https://download.bls.gov/pub/time.series/jt/jt.industry) · [JOLTS Home](https://www.bls.gov/jlt/)

---

## OEWS + Employment Projections — Occupation Dimension (OE / EP)

**Occupation is THE key axis for AI-displacement** — GenAI substitutes for *tasks bundled into occupations*, not industries/geographies per se. OEWS = rich cross-section of employment + wages by 6-digit SOC; EP = forward-looking 10-yr outlook. Neither is monthly — pair with CPS occupation data for real-time turning points.

### OEWS (OE) series ID anatomy (25 chars)
`OE` + `U`(always NSA) + areatype(1) + area(7) + industry(6) + occupation(6) + datatype(2)

| Field | Positions | Values |
|---|---|---|
| Prefix | 1–2 | `OE` |
| Seasonal | 3 | `U` (annual; no SA variant) |
| Area type | 4 | `N` national · `S` state · `M` metro |
| Area | 5–11 | `0000000` national; state FIPS padded (`0600000`=CA); 7-digit CBSA for metros |
| Industry | 12–17 | NAICS; `000000` = all industries |
| Occupation | 18–23 | **6-digit SOC, hyphen removed** (`150000` Computer & Math; `151252` Software Developers; `000000` all) |
| Data type | 24–25 | measure (below) |

**Data types:** `01` Employment · `03` hourly mean · `04` annual mean · `08` hourly median · `13` annual median · `06/07/10` hourly 10th/25th/90th pctile · `11/12/14/15` annual 10th/25th/75th/90th pctile · `16` emp per 1,000 jobs · `17` location quotient. (No `02`.)

### SOC major groups + GenAI-exposure flags
| SOC | Major group | Exposure |
|---|---|---|
| **15-0000** | Computer & Mathematical | **HIGH** |
| **43-0000** | Office & Administrative Support | **HIGH** |
| **13-0000** | Business & Financial Operations | **HIGH** |
| **23-0000** | Legal | **HIGH** |
| **27-0000** | Arts, Design, Entertainment, Sports & Media | **HIGH** |
| 11 | Management | Medium |
| 25 | Education/Library | Medium |
| 41 | Sales | Medium |
| 29 / 31 | Healthcare practitioner / support | Low–Med |
| 47/49/53/35/37/45/51 | Construction, Repair, Transport, Food, Cleaning, Farming, Production | Low |

**Priority watch-list:** SOC **15, 43, 13, 23, 27** and detailed children — 15-1252 Software Developers, 15-2051 Data Scientists, 27-3043 Writers, 23-2011 Paralegals, 43-9021 Data Entry Keyers.

### Verified examples (format confirmed via API + govex tutorial)
- `OEUN000000000000000000001` — National, all industries, all occupations, employment
- `OEUN000000000000150000­01` — National, Computer & Mathematical, employment
- `OEUN000000000000151252­04` — National, Software Developers, mean annual wage

> **API caveat:** OEWS values require the **registered key** (unregistered tier returned "No Data Available" even for known-good series). Bulk users prefer flat files `download.bls.gov/pub/time.series/oe/`.

### ⚠️ OEWS is an annual snapshot, not a time series
- Point-in-time estimate keyed to a **May reference date**, pooled from six semiannual panels over ~3 years.
- **Released once a year** with a **~9–12 month lag** → unsuitable for real-time AI inflection detection.
- **Not longitudinal:** comparability broken by 2010→2018 SOC transition and periodic NAICS/area updates. YoY deltas mix real change with reclassification.
- **Trade-off:** use **OEWS for the detailed cross-sectional structure** (which occupations, how many, wages, where) and **CPS monthly occupation series for high-frequency turning points** (coarser SOC groups but current, ~3-wk lag).

### Employment Projections (EP) — 10-yr outlook
- Per occupation: base-year & projected employment, numeric/percent change, projected annual **openings**, entry education, median wage. Current vintage **2024–2034** (total emp +3.1%; Computer & Mathematical **+10.1%**, ~3× the all-occupation average).
- **Access:** primarily the **Occupational Projections tool** (`data.bls.gov/projections/occupationProj`) and **flat files** (`bls.gov/emp/tables.htm`). An EP series form exists (`EP`+`U`+occupation(6)+industry(6)) but is **not reliably served via the standard time-series API** — treat as flat-file/matrix-tool access. Updated ~annually (database Sept; wages April).
- **Relevance:** BLS projections **incorporate automation/AI staffing assumptions** → useful structured prior, but *modeled expert projections*, not realized data, and historically slow to anticipate tech shocks. Use to frame hypotheses, validate against realized OEWS + CPS.

### Relevance to AI-impact tracking (summary)
Build around the five HIGH-exposure SOC groups. Three layers: (1) **OEWS** detailed structural baseline (annual, lagged, key-gated); (2) **EP** automation-aware forward prior (flat files); (3) **CPS monthly occupation** for turning points. Always flag OEWS annual-snapshot lag + SOC-revision breaks on any YoY occupational delta.

Sources: govex/bls-oews-api-tutorial · [OEWS](https://www.bls.gov/oes/) · [Series ID Formats](https://www.bls.gov/help/hlpforma.htm) · [Employment Projections](https://www.bls.gov/emp/) · [Occupational Projections tool](https://data.bls.gov/projections/occupationProj)

---

## AI-Exposure Mapping & Methodology References

External datasets that score occupations/tasks for AI exposure, to **join to BLS series** (CPS occupation/industry/education; OEWS; CES). All URLs verified to resolve and key confirmed.

### 1. Felten, Raj & Seamans — AI Occupational Exposure (AIOE)
- Occupation exposure linking 10 AI applications → 52 O*NET abilities. Companion **AIIE** (industry), **AIGE** (geography). GenAI-specific variants ("Language Modeling", "Image Generation").
- **Key:** AIOE by **6-digit SOC**; AIIE by **4-digit NAICS**; AIGE by **county FIPS**.
- **Data:** [github.com/AIOE-Data/AIOE](https://github.com/AIOE-Data/AIOE) (`AIOE_DataAppendix.xlsx`, plus Language/Image Modeling files). Paper: [SMJ 2021](https://sms.onlinelibrary.wiley.com/doi/full/10.1002/smj.3286).
- **Join:** SOC → OEWS direct; SOC → Census occ → CPS. AIIE → CES/QCEW on NAICS. GenAI variants are the most relevant treatment intensity.

### 2. Webb (2020) — patent-based AI exposure
- Text overlap between **patent titles** and O*NET tasks; AI skews to *high-skill* tasks (vs software/robots). Pre-LLM benchmark.
- **Data:** [webb_ai.pdf](https://www.michaelwebb.co/webb_ai.pdf), data link on [michaelwebb.co](https://www.michaelwebb.co/). **Join:** SOC → Census occ → CPS. Use in a horse-race vs GenAI exposure.

### 3. Eloundou, Manning, Mishkin & Rock (2023) — "GPTs are GPTs" ⭐
- Task/occupation exposure to LLMs (E0/E1/E2 rubric, human + GPT-4 scored). Measures: `alpha`=E1, `beta`=E1+0.5·E2, `gamma`=E1+E2. ~80% of workers have ≥10% tasks exposed.
- **Key:** O*NET tasks → **O*NET-SOC (8-digit) → 6-digit SOC**.
- **Data:** [github.com/openai/GPTs-are-GPTs](https://github.com/openai/GPTs-are-GPTs) (`data/occ_level.csv`). [arXiv:2303.10130](https://arxiv.org/abs/2303.10130). The canonical GenAI exposure / treatment-intensity variable.

### 4. Anthropic Economic Index (AEI)
- *Observed* Claude usage mapped to O*NET tasks/occupations (Clio pipeline), automation-vs-augmentation + geographic splits. Captures **actual adoption**, not capability.
- **Data:** [huggingface.co/datasets/Anthropic/EconomicIndex](https://huggingface.co/datasets/Anthropic/EconomicIndex) (releases through 2026; see each `data_documentation.md`). Hub: [anthropic.com/economic-index](https://www.anthropic.com/economic-index).
- **Join:** task/occ → SOC → Census occ (CPS) or SOC → OEWS. Best as an **adoption/mechanism covariate**.

### 5. Other usable datasets
- **OpenAI:** the usable occupation dataset is the "GPTs are GPTs" repo (§3); no separate usage panel.
- **Bruegel** GenAI task-exposure (EU, O*NET-based, [WP 06/2024](https://www.bruegel.org/system/files/2024-03/WP%2006.pdf)); **Yale Budget Lab** exposure-quintile tracking.

### 6. O*NET + crosswalk backbone
- O*NET supplies the task/ability vocabulary all indices build on; keyed on **O*NET-SOC (8-digit; first 6 = SOC)**. Collapse to 6-digit SOC first.
- Crosswalks: [O*NET Resource Center](https://www.onetcenter.org/crosswalks.html) (O*NET-SOC↔SOC); **Census** [2018 Occupation Code List + SOC crosswalk](https://www2.census.gov/programs-surveys/demo/guidance/industry-occupation/2018-occupation-code-list-and-crosswalk.xlsx) — **the bridge CPS needs** (CPS/ACS use Census occ codes, not SOC); [BLS crosswalks](https://www.bls.gov/emp/documentation/crosswalks.htm).

### 7. Treatment-date anchors (event study)
- **ChatGPT public launch — Nov 30, 2022** = primary treatment break.
- **GPT-4 — Mar 14, 2023** = secondary / dose-escalation window; late-2023 enterprise diffusion = third.
- Design: continuous exposure index (GPTs-are-GPTs `beta` or AIOE language-modeling) × post-Nov-2022 indicator; validate parallel pre-trends on CPS occupation cells back to ~2018.

### Recommended join strategy
- **Occupation (primary):** collapse each index to **6-digit SOC** → for CPS bridge **SOC → Census occ** (2018 vintage); for OEWS join SOC direct. Mind 2010 vs 2018 SOC vintages.
- **Industry:** AIIE on 4-digit NAICS → CES/QCEW/OEWS, aggregated to the series' NAICS level.
- **Education:** CPS carries attainment at microdata level (IPUMS-CPS) → employment-weighted mean of an occupation index within education×period cells.
- **Geography (optional):** AIGE (county FIPS) or AEI (state) for local-labor-market designs.

### Situating literature (the disagreement to report honestly)
- **Brynjolfsson, Chandar & Chen (2025), "Canaries in the Coal Mine"** (Stanford; ADP payroll, ~25M workers): ~13% relative employment decline for workers aged 22–25 in AI-exposed occupations since late 2022 (young software devs −~20% by Jul 2025); none for older workers/augmentation roles. [PDF](https://digitaleconomy.stanford.edu/app/uploads/2025/11/CanariesintheCoalMine_Nov25.pdf).
- **Yale Budget Lab (recurring CPS updates through 2026):** finds *no* clear AI-exposure relationship with employment/unemployment and no acceleration in occupational-mix change since ChatGPT. [AI topic hub](https://budgetlab.yale.edu/topic/artificial-intelligence). Skeptical counterweight.
- **Economic Innovation Group (2025), "AI and Jobs"** — shows index choice drives conclusions. [PDF](https://eig.org/wp-content/uploads/2025/08/EIG-AI-and-Jobs.pdf).

**Bottom line:** Stanford (payroll) finds entry-level GenAI effects; Yale (CPS) finds none. The analysis should report results under **multiple exposure indices** and **multiple outcome sources (CPS vs payroll)**, treat Nov-2022/Mar-2023 as *potential* treatment, and use AEI adoption as the mechanism check. Correlation ≠ causation; flag pre-trends explicitly.

---

## Adjacent / complementary sources beyond core BLS

Worth pulling for a complete picture; flagged so the catalog is exhaustive.

| Source | What | Why include | Access |
|---|---|---|---|
| **QCEW** (BLS `EN`) | Quarterly near-**census** of employment & wages by **county × 6-digit NAICS** | Most granular, most accurate industry×geography benchmark (covers ~95% of jobs) | BLS API / [bls.gov/cew](https://www.bls.gov/cew/) |
| **Business Employment Dynamics** (BLS `BD`) | Gross job **gains/losses**, establishment births/deaths | Churn beneath net payrolls; is hiring drying up structurally? | [bls.gov/bdm](https://www.bls.gov/bdm/) |
| **UI weekly claims** (DOL/ETA — *not* BLS) | **Initial & continued** jobless claims, weekly, by state | Highest-frequency labor signal; earliest read on layoffs | [oui.doleta.gov](https://oui.doleta.gov/unemploy/claims.asp), FRED `ICSA`/`CCSA` |
| **WARN notices** (state agencies) | Mandated mass-layoff notices, firm-level | Names actual employers/tech layoffs in near-real-time | Per-state portals |
| **Challenger, Gray & Christmas** (private) | Monthly job-cut announcements **by reason** (now tags "AI" / "technological update") | One of the only sources attributing cuts to AI directly | Press releases / paid |
| **ECEC / ECI** (BLS `CM`/`CI`) | Employer compensation cost / employment cost index | Wage-pressure cross-check | BLS API |

---

## Priority shortlist — minimal AI-tracker panel

The smallest series set that answers "has AI taken a toll?" (fits in one ≤50-series API request):

**National baseline:** `LNS14000000` (UR), `LNS11300000` (LFPR), `LNS12300000` (emp-pop), `LNS13000000` (unemployment level), `LNS13008276` (median duration), `LNS13092836` (27+wk share).
**Education gradient ⭐:** `LNS14027659`, `LNS14027660`, `LNS14027689`, `LNS14027662`.
**AI-exposed industry employment ⭐:** `CES5000000001` (Information), `CES6000000001` (PBS) vs `CES0000000001` (total nonfarm); + hours `CES0500000002`.
**Labor-demand flows ⭐:** `JTS000000000000000JOL`, `JTS000000000000000HIL`, `JTS000000000000000QUR`, `JTS510000000000000JOL`, `JTS540099000000000JOL`, `JTS540099000000000HIL`.
**Geography (AI-dense metros):** `LAUMT063108000000003` (LA), plus SF/San Jose/Seattle/Austin/NYC `LAUMT…03`.
**Occupation structure (annual):** OEWS `OEUN…150000…01` (Computer & Math employment) + detailed children, joined to GPTs-are-GPTs `beta` and AIOE.

**Tightness ratio (derived):** `LNS13000000` ÷ `JTS000000000000000JOL`.
**Treatment break:** Nov 2022 (ChatGPT).

---

*Compiled 2026-06-08. All core BLS series IDs verified against the BLS Public Data API v2 / authoritative flat files. Next step (deferred per request): design the fetch+cache pipeline and HTML/Plotly report.*
