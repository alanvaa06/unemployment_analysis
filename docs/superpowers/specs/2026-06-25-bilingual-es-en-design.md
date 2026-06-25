# Bilingual ES/EN Dashboard

**Status:** design approved 2026-06-25.
**Owner:** Alan Vazquez
**Repo:** https://github.com/alanvaa06/unemployment_analysis
**Builds on:** `docs/superpowers/specs/2026-06-25-github-pages-publish-design.md`

## Goal

Serve the dashboard in Spanish and English with a one-click toggle, hosted on the
same GitHub Pages site. Spanish is the default (audience is Mexico). Two static
pages built from one translated codebase; the toggle is a link between them.

## Decisions (locked in brainstorming)

- **Scope:** everything visible is translated — hero, KPIs, nav, all chart text
  (titles, axes, annotations, hovertemplates, series names), the findings prose,
  disclaimer, and sources.
- **Default language:** Spanish. `index.html` = Spanish, `en.html` = English. The
  live URL flips to Spanish by default; English moves to `en.html`.
- **Translation ownership:** Claude drafts all Spanish using standard BLS/econ
  terminology and flags uncertain terms; Alan reviews before publish (native
  speaker + economist = the quality gate).
- **Toggle:** plain `ES | EN` link control, no JS state, no language memory.

## Architecture

Build-time translation. A single English-keyed translation table drives a `t()`
lookup that is threaded through the existing build as a `lang` parameter. Each
language is rendered to its own self-contained static HTML via the existing
render path (no client-side relabeling). This fits the current design, where 6 of
10 charts are server-rendered.

### 1. Translation table — `dashboard/translations.json` + `dashboard/i18n.py` (new)

The Spanish lives in a committed, reviewable `dashboard/translations.json` (a list
of `{english, spanish, uncertain, note}`, 194 entries, produced by the
extract+translate workflow). `i18n.py` loads it into a dict and exposes `t()`:

```python
import json
from pathlib import Path

_DATA = json.loads((Path(__file__).parent / "translations.json").read_text(encoding="utf-8"))
ES: dict[str, str] = {row["english"]: row["spanish"] for row in _DATA}

def t(s: str, lang: str = "es") -> str:
    """Translate an English source string. lang='en' is identity."""
    if lang == "en":
        return s
    return ES.get(s, s)   # missing → English fallback (visible, never crashes)
```

Alan reviews/edits the Spanish directly in `translations.json`; no code change
needed to correct a term.

- The **English string is its own key** — no invented IDs, minimal churn, EN path
  is identity.
- Missing translation falls back to English (caught by the coverage test +
  Alan's ES browser review, not by a crash).
- Same-English-different-Spanish collisions are not expected in this content. If
  one appears during translation, handle it then (e.g. reword the English source
  so the key is unique). Not designed for upfront.

### 2. Thread `lang` through the build

- `build_interactive(cache_dir, out_path, static=False, lang="es")`.
- Wrap every user-facing literal in `t(..., lang)`:
  - `interactive_build.py`: kicker, h1, lede, KPI labels, nav, findings prose,
    footer disclaimer + sources, toolbar labels.
  - `charts.py`, `charts_advanced.py`, `advanced.py`, `prepare.py`: Plotly
    `title`, `xaxis_title`, `yaxis_title`, `annotation` text, `hovertemplate`,
    trace `name`.
- Functions that produce text take a `lang` argument passed down from
  `build_interactive`.
- `<html lang="{lang}">` set per page.

### 3. Toggle UI

- A segmented `ES | EN` control in the existing dark toolbar, right side, next to
  the PDF button. Current language highlighted with `--clay`.
- Each side is a plain anchor: `ES` → `index.html`, `EN` → `en.html`. No
  JavaScript, no `localStorage`.
- Rendered by a helper `_lang_toggle_html(lang)` so both pages get the control
  with the correct side highlighted.
- Present in both static and non-static (Flask) builds.

### 4. SEO hints

In `<head>` of both pages:

```html
<link rel="alternate" hreflang="es" href="https://alanvaa06.github.io/unemployment_analysis/index.html">
<link rel="alternate" hreflang="en" href="https://alanvaa06.github.io/unemployment_analysis/en.html">
<link rel="alternate" hreflang="x-default" href="https://alanvaa06.github.io/unemployment_analysis/index.html">
```

### 5. Publish — `dashboard/publish.py`

```python
def publish(es_path=Path("index.html"), en_path=Path("en.html")) -> list[Path]:
    return [
        build_interactive(out_path=es_path, static=True, lang="es"),
        build_interactive(out_path=en_path, static=True, lang="en"),
    ]
```

`python -m dashboard.publish` writes both pages.

## Toggle behavior

The toggle reloads the other page, so the baseline/compare date selection resets
to its defaults. Accepted as the simplest behavior. Remembering language and
preserving chart state across the switch are explicitly out of scope.

## Testing

1. `t()` unit tests: ES key maps to Spanish; `lang="en"` returns input unchanged;
   unknown key falls back to the input string.
2. **Coverage test:** a canonical `SOURCE_STRINGS` list (the full set of English
   UI strings) → assert every entry has an `ES` key. This is the guard against a
   missed translation.
3. `_lang_toggle_html("es")` highlights ES and links `en.html`; `("en")`
   highlights EN and links `index.html`.
4. Build both languages (needs local `data/cache`): assert `index.html` contains
   representative ES strings and `lang="es"`; `en.html` contains the English
   equivalents and `lang="en"`.
5. Manual review in the browser, Spanish page — Alan's terminology gate before
   publish.

## Rollout

1. Land code + translations on `feat/bilingual-es-en`, tests green.
2. Alan reviews the Spanish (browser).
3. Apply corrections, rebuild both pages.
4. Merge to `main`, push, re-trigger one Pages build (single build — avoid the
   concurrent-build cancellation seen during the initial publish).

## Out of scope (YAGNI)

- Language memory / auto-redirect / `navigator.language` detection.
- URL-encoded chart state preserved across the toggle.
- Number, date, or currency localization (numerals unchanged).
- A third language; RTL support.
- CI auto-build (re-publish stays a local command).
