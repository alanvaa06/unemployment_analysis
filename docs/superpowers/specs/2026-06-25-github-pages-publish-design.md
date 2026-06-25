# Publish the Unemployment Dashboard to GitHub Pages

**Status:** design approved 2026-06-25.
**Owner:** Alan Vazquez
**Repo:** https://github.com/alanvaa06/unemployment_analysis

## Goal

Make the existing interactive unemployment dashboard a live, publicly hosted web
app on GitHub Pages, with a one-command local publish step. No CI, no secrets, no
backend.

## Context

- `dashboard/interactive_build.py::build_interactive()` already produces a
  **self-contained** interactive HTML (`output/dashboard.html`, ~1.5MB): embedded
  monthly series JSON (~320KB), client-side recompute of leaderboard/scatter/
  sector charts, Plotly loaded from CDN. No server needed to *view* it.
- `app.py` is a local Flask server providing `/api/refresh` (re-fetch BLS) and
  `/api/export/data.xlsx`. These endpoints do **not** exist on static hosting.
- The build already degrades gracefully when not served: `btn-pdf` uses
  `window.print()` (works anywhere); `btn-xlsx` and the refresh path are guarded
  by a `served()` check that `alert()`s instead of breaking.
- `output/` and `data/cache/` are gitignored; the built HTML is currently never
  committed. Repo is already public.

## Approach (chosen)

Build locally, commit the static HTML to the repo root, serve via GitHub Pages
from `main`/root. No GitHub Actions. Re-publish = re-run the command and push.

Rejected alternative: GitHub Actions auto-build + deploy. Requires `BLS_API_KEY`
as a repo secret and running the data pipeline in CI (cache is gitignored). More
power (self-refresh) but more failure modes. Out of scope; revisit only if
auto-refresh is wanted later.

## Changes

### 1. `dashboard/interactive_build.py` — static mode

Add `static: bool = False` to `build_interactive(...)`.

When `static=True`:
- Omit the two server-only toolbar buttons: `btn-refresh` and `btn-xlsx`.
- Keep `btn-pdf` (client-side `window.print()`).
- Everything else unchanged (embedded JSON, client recompute, Plotly CDN, theme).

Implementation: thread `static` into the toolbar HTML assembly and `_toolbar_js`
so the removed buttons and their listeners are not emitted. Default `False`
preserves current local/Flask behavior exactly.

### 2. `dashboard/publish.py` (new)

Thin module with `__main__`:

```python
from pathlib import Path
from dashboard.interactive_build import build_interactive

def publish(out_path: Path = Path("index.html")) -> Path:
    return build_interactive(out_path=out_path, static=True)

if __name__ == "__main__":
    print(publish())
```

Run: `python -m dashboard.publish` → writes repo-root `index.html`.

### 3. `.nojekyll` (new, empty, repo root)

Disables Jekyll processing on Pages. Standard practice for hand-built static HTML.

### 4. `index.html` (generated, committed at repo root)

The published app. ~1.5MB, self-contained. Root placement keeps the hand-written
`docs/` tree clean. Not gitignored (only `output/` is).

### 5. Enable GitHub Pages

Programmatically via `gh`:

```
gh api -X POST repos/alanvaa06/unemployment_analysis/pages \
  -f 'source[branch]=main' -f 'source[path]=/'
```

(Exact flag form to be confirmed at implementation — `gh` nested-field syntax.)
Requires `gh` auth with repo admin. Fallback: Settings → Pages → Source =
`main` / `/ (root)`. Live URL: `https://alanvaa06.github.io/unemployment_analysis/`.

### 6. `README.md`

Add the live URL and the publish step:
`python -m dashboard.publish` then commit + push `index.html`.

## Data freshness

The page is a snapshot baked at publish time. There is no live refresh on Pages
(that remains the local Flask app's role). Updating the public site means
re-running `python -m dashboard.publish` and pushing.

## Verification

1. `python -m dashboard.publish` writes `index.html` at root.
2. Open `index.html` directly (file://) — toolbar shows **no** Refresh/Excel
   buttons; PDF button present; charts and the baseline/compare control work.
3. Existing 53 tests stay green.
4. New test: `build_interactive(static=True)` output excludes the substrings
   `btn-refresh` and `id="btn-xlsx"`; `static=False` still includes them.
5. After push + Pages enable: fetch the live URL, confirm HTTP 200 and the page
   title renders.

## Out of scope (YAGNI)

- CI auto-build / scheduled refresh.
- Client-side Excel/CSV export.
- Custom domain.
- Any change to the dashboard's content, charts, or theme.
