# Bilingual ES/EN Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the dashboard in Spanish (default) and English from one codebase, with a `ES | EN` toggle, both served as static pages on GitHub Pages.

**Architecture:** Build-time translation. A committed `dashboard/translations.json` (English→Spanish, 194 strings, already produced) backs a `t(s, lang)` lookup in a new `dashboard/i18n.py`. A `lang` parameter is threaded from `build_interactive` into every text-producing function; each chart builder wraps its user-facing literals with `t(..., lang)`. `publish.py` renders both `index.html` (es) and `en.html` (en). The toggle is a plain link between the two pages.

**Tech Stack:** Python 3, pytest, Plotly, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-06-25-bilingual-es-en-design.md`
**Branch:** `feat/bilingual-es-en` (spec + `translations.json` already committed).

## Reference: the translation source

`dashboard/translations.json` is a list of `{english, spanish, uncertain, note}`. It
is the single source of truth. When a task says "wrap the strings in file X",
the exact English strings for that file are the `english` values the extractor
tagged to X (see the spec's workflow). The wrapping rule is always the same:

> Replace a user-facing English literal `"Foo"` with `t("Foo", lang)`, where the
> `t` lookup returns the Spanish for `lang="es"` and `"Foo"` itself for `lang="en"`.

For hovertemplates/format strings, wrap **only the human-readable label**, never
the format tokens:

```python
# before
hovertemplate="Openings: %{y:.0f}k<extra></extra>"
# after
hovertemplate=f"{t('Openings', lang)}: %{{y:.0f}}k<extra></extra>"
```

(Note the `%{{...}}` doubling once the string becomes an f-string.)

---

### Task 1: `dashboard/i18n.py` — translation lookup

**Files:**
- Create: `dashboard/i18n.py`
- Test: `tests/test_i18n.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_i18n.py`:

```python
"""Translation lookup and coverage."""
import json
from pathlib import Path

from dashboard import i18n


def test_t_es_translates_known_string():
    assert i18n.t("Unemployment rate", "es") == "Tasa de desempleo"


def test_t_en_is_identity():
    assert i18n.t("Unemployment rate", "en") == "Unemployment rate"
    assert i18n.t("anything at all", "en") == "anything at all"


def test_t_unknown_falls_back_to_input():
    assert i18n.t("a string with no translation", "es") == "a string with no translation"


def test_t_default_lang_is_es():
    assert i18n.t("Job openings") == "Vacantes"


def test_table_has_no_empty_spanish():
    data = json.loads(
        (Path(i18n.__file__).parent / "translations.json").read_text(encoding="utf-8"))
    assert data, "translations.json is empty"
    assert all(row["spanish"].strip() for row in data), "an entry has empty Spanish"


def test_critical_terms_present():
    # guards against a future edit dropping a key string
    for s in ["Unemployment rate", "Job openings", "Findings",
              "Has AI taken a toll on jobs?", "Where the jobs went"]:
        assert i18n.t(s, "es") != s, f"missing translation for {s!r}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_i18n.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dashboard.i18n'`

- [ ] **Step 3: Create the module**

Create `dashboard/i18n.py`:

```python
"""Build-time i18n. English source strings map to Spanish via translations.json.

t(s, "en") is identity; t(s, "es") returns the Spanish or falls back to s.
The English string is its own key — no invented IDs.
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA = json.loads(
    (Path(__file__).parent / "translations.json").read_text(encoding="utf-8"))

ES: dict[str, str] = {row["english"]: row["spanish"] for row in _DATA}


def t(s: str, lang: str = "es") -> str:
    if lang == "en":
        return s
    return ES.get(s, s)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_i18n.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add dashboard/i18n.py tests/test_i18n.py
git commit -m "feat: i18n lookup backed by translations.json"
```

---

### Task 2: Language toggle helper

**Files:**
- Modify: `dashboard/interactive_build.py` (add `_lang_toggle_html`; place it next to `_toolbar_html`)
- Test: `tests/test_publish.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_publish.py`:

```python
def test_lang_toggle_es_highlights_es_and_links_en():
    h = ib._lang_toggle_html("es")
    assert 'href="en.html"' in h
    assert "ES" in h and "EN" in h
    assert "is-active" in h          # current language marked active

def test_lang_toggle_en_highlights_en_and_links_es():
    h = ib._lang_toggle_html("en")
    assert 'href="index.html"' in h
    assert "is-active" in h
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_publish.py -k lang_toggle -v`
Expected: FAIL — `AttributeError: ... has no attribute '_lang_toggle_html'`

- [ ] **Step 3: Implement the helper**

In `dashboard/interactive_build.py`, add near `_toolbar_html`:

```python
def _lang_toggle_html(lang: str = "es") -> str:
    es_cls = " is-active" if lang == "es" else ""
    en_cls = " is-active" if lang == "en" else ""
    return (
        '<span class="langtoggle">'
        f'<a class="lang{es_cls}" href="index.html" hreflang="es">ES</a>'
        f'<a class="lang{en_cls}" href="en.html" hreflang="en">EN</a>'
        '</span>'
    )
```

- [ ] **Step 4: Add toggle CSS**

In `_CONTROL_CSS` (top of `interactive_build.py`), append:

```css
.langtoggle{display:inline-flex;border:1px solid #4a4b54;border-radius:8px;overflow:hidden;margin-left:6px}
.langtoggle .lang{font-family:var(--sans);font-size:.8rem;font-weight:600;padding:7px 11px;color:var(--paper);background:#34353e;text-decoration:none}
.langtoggle .lang+.lang{border-left:1px solid #4a4b54}
.langtoggle .lang.is-active{background:var(--clay);color:var(--paper)}
.langtoggle .lang:hover:not(.is-active){background:var(--clay-strong)}
```

- [ ] **Step 5: Render the toggle in the toolbar**

In `_toolbar_html(static, lang)` (signature updated in Task 3), append the toggle
after the PDF button in BOTH the static and full branches:

```python
    return ('<div class="toolbar"><div class="wrap">\n'
            '  <span class="brand">' + t("AI & US jobs", lang) + '</span>\n'
            f'{buttons}\n'
            f'  {_lang_toggle_html(lang)}\n'
            '</div></div>')
```

- [ ] **Step 6: Run to verify it passes**

Run: `python -m pytest tests/test_publish.py -k lang_toggle -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add dashboard/interactive_build.py tests/test_publish.py
git commit -m "feat: ES|EN language toggle control"
```

---

### Task 3: Thread `lang` through `build_interactive` and translate `interactive_build.py`

This is the largest task: the page template plus 116 strings. Wrap every
user-facing literal in `interactive_build.py` with `t(..., lang)` and pass `lang`
to every chart builder call.

**Files:**
- Modify: `dashboard/interactive_build.py`

- [ ] **Step 1: Import `t` and add the param**

At the top: `from dashboard.i18n import t`.

Change the signature:

```python
def build_interactive(cache_dir: Path = Path("data/cache"),
                      out_path: Path = Path("output/dashboard.html"),
                      static: bool = False,
                      lang: str = "es") -> Path:
```

Thread `lang` into the helpers: `_toolbar_html(static, lang)`,
`_overlay_html(static, lang)` (signatures gain `lang`), and set
`<html lang="{lang}">` in the template head (currently `lang="en"`).

- [ ] **Step 2: Wrap the page-chrome literals**

Wrap every user-facing string in the f-string template and the helper functions
with `t(..., lang)`. These are the `interactive_build.py` entries in
`translations.json` (kicker, h1, lede, KPI labels, section eyebrows/titles/
captions, the six findings, nav labels, footer, toolbar titles, overlay text,
JS `alert()` strings). Example for the hero:

```python
f'<p class="kicker">{t("US labor market, an interactive BLS data view", lang)}</p>'
f'<h1>{t("Has AI taken a toll on jobs?", lang)}</h1>'
f'<p class="lede">{t("Nine hundred BLS series, explorable. Pick any two dates and the decompositions, distributions, and relationships below all recompute. Data through {asof}.", lang).format(asof=asof)}</p>'
```

Note the `{asof}` pattern: the translation keeps the literal `{asof}` token, so
call `.format(asof=asof)` AFTER `t(...)`. Apply the same to the footer "Sources"
line (it also contains `{asof}`).

The `<title>` tag uses `t("Has AI taken a toll on jobs? An interactive view", lang)`.

- [ ] **Step 3: Pass `lang` to every chart builder call**

Every call that builds a figure or chart HTML gets `lang=lang`. The builders gain
the param in Tasks 4-6. Example:

```python
es = advanced.event_study_indexed(obs, "2022-11", "CES5000000001", ["CES0500000001"])
fig = charts_advanced.fig_event_study(es, lang=lang)
```

KPI labels dict — wrap the keys' display text:

```python
kpis = {t("Unemployment rate", lang): _fmt(k["unemployment_rate"], "%"),
        t("Participation", lang): _fmt(k["lfpr"], "%"),
        t("Bachelor's+ UR", lang): _fmt(k["ur_bachelors"], "%"),
        t("Job openings", lang): _fmt(k["openings"], "k", 0),
        t("Quits rate", lang): _fmt(k["quits_rate"], "%")}
```

Section eyebrow `"Exhibit"` and the findings header `"Six findings from 900 series"`
and nav labels likewise wrapped with `t(..., lang)`.

- [ ] **Step 4: Update existing call sites and the JS `served()` strings**

`_toolbar_js` static branch is language-agnostic (only `window.print()`), no
change. The non-static branch's `alert(...)` strings are wrapped with `t(...)`
ONLY if they render in the published page — they belong to the Flask path, which
is always English-safe; wrap them with `t(..., lang)` for completeness using the
`translations.json` entries (e.g. "Open via the local app (python app.py) to
refresh from BLS.").

- [ ] **Step 5: Build both languages (needs local `data/cache`)**

```powershell
python -c "from pathlib import Path; from dashboard.interactive_build import build_interactive as b; b(out_path=Path('output/_es.html'), static=True, lang='es'); b(out_path=Path('output/_en.html'), static=True, lang='en'); print('ok')"
```

Verify:

```bash
python - <<'PY'
es=open('output/_es.html',encoding='utf-8').read(); en=open('output/_en.html',encoding='utf-8').read()
print('es lang attr', 'lang="es"' in es)
print('en lang attr', 'lang="en"' in en)
print('es has Tasa de desempleo', 'Tasa de desempleo' in es)
print('es has hero ES', '¿La IA' in es or 'IA' in es)   # hero h1 translated
print('en still English', 'Has AI taken a toll on jobs?' in en)
print('es NOT leaking EN hero', 'Has AI taken a toll on jobs?' not in es.split('</title>')[1][:4000])
PY
```

Expected: es lang true, en lang true, es has Spanish KPI, en still English. Delete the temp files.

- [ ] **Step 6: Commit**

```bash
git add dashboard/interactive_build.py
git commit -m "feat: thread lang through build_interactive; translate page chrome"
```

---

### Task 4: Translate `dashboard/charts.py`

**Files:**
- Modify: `dashboard/charts.py`

- [ ] **Step 1: Import and add `lang` to the public `fig_*` builders**

`from dashboard.i18n import t`. Add `lang: str = "es"` to each `fig_*` function
that `interactive_build.py` actually calls, and wrap its user-facing literals
(titles, `xaxis_title`/`yaxis_title`, trace `name=`, annotation text, the
human label in `hovertemplate`). The `charts.py` strings in `translations.json`
are the full set (education trace names, JOLTS labels, "ChatGPT (Nov 2022)",
"Index, Nov 2022 = 100", etc.). Example:

```python
def fig_education(edu: pd.DataFrame, lang: str = "es") -> go.Figure:
    ...
    fig.add_scatter(..., name=t("Bachelor's and higher", lang))
    fig.update_yaxes(title_text=t("UR %", lang))
```

The `_chatgpt_marker` annotation `"ChatGPT (Nov 2022)"` → wrap with `t(..., lang)`;
pass `lang` into `_chatgpt_marker(fig, lang)`.

- [ ] **Step 2: Build-assert (es) for this file's charts**

After wiring, rebuild es (Task 3 Step 5 command) and assert a representative
charts.py string is translated, e.g. `"Tasa de renuncias"` is unnecessary here;
use `"Índice, nov 2022 = 100"`-style check against the actual Spanish in
`translations.json` for `"Index, Nov 2022 = 100"`.

```bash
python - <<'PY'
import json
m={r['english']:r['spanish'] for r in json.load(open('dashboard/translations.json',encoding='utf-8'))}
es=open('output/_es.html',encoding='utf-8').read()
for k in ["Index, Nov 2022 = 100","Bachelor's and higher"]:
    print(k, '→', m[k], ':', m[k] in es)
PY
```

Expected: each Spanish string present in the es build.

- [ ] **Step 3: Run the full suite + commit**

Run: `python -m pytest -q` → all green.

```bash
git add dashboard/charts.py
git commit -m "feat: translate charts.py figure text"
```

---

### Task 5: Translate `dashboard/charts_advanced.py`

**Files:**
- Modify: `dashboard/charts_advanced.py`

- [ ] **Step 1: Add `lang` to each `fig_*` builder and wrap literals**

`from dashboard.i18n import t`. Add `lang: str = "es"` to `fig_industry_heatmap`,
`fig_state_ur_boxplot`, `fig_state_ur_choropleth_animated`, `fig_event_study`,
`fig_beveridge`, `fig_dispersion_fan`, `fig_education_gap`, `fig_diffusion`,
`fig_change_histogram` (the ones `interactive_build` calls). Wrap their titles,
axis titles, trace names, annotations (`"ChatGPT"`, `"GPT-4"`, `"Year:"`,
`"Play"`, `"Pause"`, `"breadth-neutral"`, `"balance"`), and hovertemplate labels
(`"Control"`, `"Information"`, `"UR"`, `"std"`). All listed under
`charts_advanced.py` in `translations.json`.

- [ ] **Step 2: Build-assert (es) + commit**

Rebuild es; assert e.g. `"Tasa de vacantes"` (`Job-openings rate`) and
`"Estudio de eventos"` region strings present. Run `python -m pytest -q` green.

```bash
git add dashboard/charts_advanced.py
git commit -m "feat: translate charts_advanced.py figure text"
```

---

### Task 6: Translate `dashboard/advanced.py` and `dashboard/prepare.py`

**Files:**
- Modify: `dashboard/advanced.py`, `dashboard/prepare.py`

- [ ] **Step 1: `advanced.py` — wrap the industry/series labels**

`from dashboard.i18n import t`. The 24 `advanced.py` strings are mostly
`LEAF_PARTITION` industry display names ("Mining & logging", "Construction",
"Durable goods mfg", "Wholesale trade", "Retail trade",
"Transportation & warehousing", …) and the `"AI-exposed"`/`"Other"`/
`"Information"` labels used by the distribution/bundle builders. Add
`lang: str = "es"` to the functions that emit these labels
(`contribution_waterfall`, `industry_change_distribution`, `change_distribution`,
`advanced_bundle`, `freeze_vs_cuts`, `exposure_industry_change`,
`state_ur_change_techshare` as applicable) and wrap the label literals with
`t(..., lang)`. `interactive_build` passes `lang`.

- [ ] **Step 2: `prepare.py` — wrap the 3 labels**

The `prepare.py` strings are `"Information"` (and the two others the extractor
tagged). Add `lang` where these display labels are produced and wrap with
`t(..., lang)`. If a label is a data key used for joins elsewhere, translate only
the **display** copy, not the join key — verify the value is not used as a lookup
key before wrapping.

- [ ] **Step 3: Build-assert (es) + full suite + commit**

Rebuild es; assert `"Manufactura de bienes duraderos"`-style Spanish (for
`"Durable goods mfg"`) present. Run `python -m pytest -q` green.

```bash
git add dashboard/advanced.py dashboard/prepare.py
git commit -m "feat: translate advanced.py and prepare.py labels"
```

---

### Task 7: Publish both pages

**Files:**
- Modify: `dashboard/publish.py`
- Modify: `dashboard/interactive_build.py` (hreflang tags)
- Test: `tests/test_publish.py` (update the existing publish test)

- [ ] **Step 1: Update the publish delegation test**

Replace `test_publish_delegates_static_to_root_index` in `tests/test_publish.py`:

```python
def test_publish_builds_both_languages(monkeypatch):
    from dashboard import publish as pub
    calls = []
    def fake_build(out_path, static, lang):
        calls.append((Path(out_path), static, lang))
        return Path(out_path)
    monkeypatch.setattr(pub, "build_interactive", fake_build)
    result = pub.publish()
    assert (Path("index.html"), True, "es") in calls
    assert (Path("en.html"), True, "en") in calls
    assert result == [Path("index.html"), Path("en.html")]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_publish.py -k both_languages -v`
Expected: FAIL (publish still single-page / wrong signature).

- [ ] **Step 3: Update `publish.py`**

```python
def publish(es_path: Path = Path("index.html"),
            en_path: Path = Path("en.html")) -> list[Path]:
    return [
        build_interactive(out_path=es_path, static=True, lang="es"),
        build_interactive(out_path=en_path, static=True, lang="en"),
    ]


if __name__ == "__main__":
    for p in publish():
        print(p)
```

- [ ] **Step 4: Add hreflang tags**

In the `<head>` of the template in `interactive_build.py`, after the `<title>`:

```python
'<link rel="alternate" hreflang="es" href="https://alanvaa06.github.io/unemployment_analysis/index.html">'
'<link rel="alternate" hreflang="en" href="https://alanvaa06.github.io/unemployment_analysis/en.html">'
'<link rel="alternate" hreflang="x-default" href="https://alanvaa06.github.io/unemployment_analysis/index.html">'
```

- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest tests/test_publish.py -k both_languages -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add dashboard/publish.py dashboard/interactive_build.py tests/test_publish.py
git commit -m "feat: publish builds index.html (es) + en.html (en) with hreflang"
```

---

### Task 8: Integration build + regression + browser review

**Files:** none (verification + generated `index.html`, `en.html`)

- [ ] **Step 1: Build both real pages**

Run: `python -m dashboard.publish`
Expected: prints `index.html` and `en.html`.

- [ ] **Step 2: Automated leak check**

```bash
python - <<'PY'
import json
m={r['english']:r['spanish'] for r in json.load(open('dashboard/translations.json',encoding='utf-8'))}
es=open('index.html',encoding='utf-8').read()
en=open('en.html',encoding='utf-8').read()
assert 'lang="es"' in es and 'lang="en"' in en
# every Spanish string for non-trivial entries should appear in es build
miss=[k for k,v in m.items() if len(k)>6 and v!=k and v not in es]
print('es lang ok; en lang ok')
print('untranslated-in-es (sample):', miss[:15])
print('count missing:', len(miss))
# toggle present on both
print('es toggle', 'langtoggle' in es, '| en toggle', 'langtoggle' in en)
PY
```

Expected: `count missing` is 0 (or only known dynamic `{asof}` strings). Investigate any miss — it means a literal was not wrapped.

- [ ] **Step 3: Full test suite**

Run: `python -m pytest -q`
Expected: all green.

- [ ] **Step 4: Browser review (Alan's translation gate)**

Open `index.html` in a browser. Confirm: page is Spanish end-to-end (hero, KPIs,
nav, all 10 chart titles/axes/annotations, findings, footer); the `ES | EN`
toggle shows ES active; clicking `EN` loads the English page; charts render and
the date control still recomputes. Note any awkward term.

- [ ] **Step 5: Apply translation corrections**

For any term flagged in review or in the 56 `uncertain` entries, edit
`dashboard/translations.json` (Spanish only), then `python -m dashboard.publish`
again. Commit:

```bash
git add dashboard/translations.json index.html en.html
git commit -m "feat: build bilingual pages; apply translation review"
```

---

### Task 9: Deploy

- [ ] **Step 1: Merge to main**

```bash
git checkout main
git merge --no-ff feat/bilingual-es-en -m "feat: bilingual ES/EN dashboard"
```

- [ ] **Step 2: Push**

```bash
git push origin main
```

- [ ] **Step 3: Trigger ONE Pages build (avoid the concurrent-build cancellation)**

```bash
gh api -X POST repos/alanvaa06/unemployment_analysis/pages/builds >/dev/null
```

- [ ] **Step 4: Verify live (both pages)**

Poll until built, then:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://alanvaa06.github.io/unemployment_analysis/
curl -s -o /dev/null -w "%{http_code}\n" https://alanvaa06.github.io/unemployment_analysis/en.html
```

Expected: `200` for both. Spot-check the live Spanish page has `lang="es"` and the
toggle.

- [ ] **Step 5: Update project logs**

Append one line to `docs/context/sesion-log.md`, add a decision to
`docs/context/memory.md`, mark the bilingual todo done in `docs/context/todo.md`.
Commit + push.

---

## Self-Review

- **Spec coverage:** scope=everything (Tasks 3-6 wrap all 194 strings) ✓;
  ES default index.html + en.html (Task 7) ✓; translation table mechanism
  (Task 1, JSON-backed — refinement of the spec's inline-dict; same intent) ✓;
  toggle plain link (Task 2) ✓; hreflang (Task 7) ✓; toggle resets selection =
  accepted (no state code) ✓; tests incl. coverage (Tasks 1,8) ✓; rollout single
  build (Task 9) ✓; translation ownership = Alan reviews (Task 8 Step 4-5) ✓.
- **Placeholder scan:** wrapping tasks reference `translations.json` for the
  per-file string list rather than re-listing 194 strings inline; the wrap rule +
  representative concrete examples are given. This is intentional for mechanical
  repetition, not a placeholder.
- **Type consistency:** `t(s, lang="es")`, `build_interactive(..., lang="es")`,
  `_toolbar_html(static, lang)`, `_overlay_html(static, lang)`,
  `_lang_toggle_html(lang)`, `publish() -> list[Path]`, and `fig_*(..., lang="es")`
  are consistent across tasks.
- **Risk:** `prepare.py`/`advanced.py` labels may double as join keys — Task 6
  Step 2 calls out verifying display-vs-key before wrapping. The leak check
  (Task 8 Step 2) is the backstop against any un-wrapped literal.
