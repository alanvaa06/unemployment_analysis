# GitHub Pages Publish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the existing interactive unemployment dashboard as a static GitHub Pages site, driven by one local command.

**Architecture:** Add a `static` mode to `build_interactive()` that drops the two server-only toolbar buttons (Refresh, Excel) and the refresh overlay/JS, keeping the client-side PDF button. A thin `dashboard/publish.py` builds straight to repo-root `index.html`. Commit that file plus `.nojekyll`, merge to `main`, enable Pages from `main`/root.

**Tech Stack:** Python 3, pytest, existing Plotly-based dashboard, GitHub Pages, `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-06-25-github-pages-publish-design.md`

**Branch:** `feat/github-pages-publish` (already created; spec already committed).

---

### Task 1: Static-aware toolbar HTML + JS helpers

Extract the inline toolbar/overlay markup into pure helper functions gated by a
`static` flag, and add the flag to `_toolbar_js`. Pure string functions — unit
testable with no data dependency.

**Files:**
- Modify: `dashboard/interactive_build.py` (add `_toolbar_html`, `_overlay_html`; add `static` param to `_toolbar_js` at lines 443-476)
- Test: `tests/test_publish.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_publish.py`:

```python
"""Static-publish mode: toolbar/JS helpers drop server-only controls."""
from dashboard import interactive_build as ib


def test_toolbar_html_full_has_server_buttons():
    h = ib._toolbar_html(static=False)
    assert 'id="btn-refresh"' in h
    assert 'id="btn-xlsx"' in h
    assert 'id="bls-key"' in h
    assert 'id="btn-pdf"' in h


def test_toolbar_html_static_drops_server_buttons():
    h = ib._toolbar_html(static=True)
    assert 'id="btn-refresh"' not in h
    assert 'id="btn-xlsx"' not in h
    assert 'id="bls-key"' not in h
    assert 'id="btn-pdf"' in h          # client-side PDF stays


def test_overlay_html_static_is_empty():
    assert ib._overlay_html(static=True) == ""
    assert 'id="overlay"' in ib._overlay_html(static=False)


def test_toolbar_js_static_only_wires_pdf():
    js = ib._toolbar_js(static=True)
    assert "window.print()" in js
    assert "btn-refresh" not in js
    assert "/api/refresh" not in js
    assert "/api/export" not in js


def test_toolbar_js_full_wires_server_actions():
    js = ib._toolbar_js(static=False)
    assert "/api/refresh" in js
    assert "/api/export" in js
    assert "window.print()" in js
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_publish.py -v`
Expected: FAIL — `AttributeError: module 'dashboard.interactive_build' has no attribute '_toolbar_html'`

- [ ] **Step 3: Add the helper functions**

In `dashboard/interactive_build.py`, add these two functions just above
`def _toolbar_js(` (around line 443):

```python
def _toolbar_html(static: bool = False) -> str:
    pdf = ('  <button id="btn-pdf" title="Open the browser print dialog; '
           'choose Save as PDF">&#x2913; PDF</button>')
    if static:
        buttons = pdf
    else:
        buttons = (
            '  <input id="bls-key" type="password" autocomplete="off" '
            'placeholder="BLS API key (optional; uses .env default)">\n'
            '  <button id="btn-refresh" class="primary" '
            'title="Re-fetch the latest data from the BLS API">'
            '&#x21bb; Refresh from BLS</button>\n'
            f'{pdf}\n'
            '  <button id="btn-xlsx" '
            'title="Download every chart&#39;s data, one sheet per chart">'
            '&#x2913; Data (Excel)</button>'
        )
    return ('<div class="toolbar"><div class="wrap">\n'
            '  <span class="brand">AI &amp; US jobs</span>\n'
            f'{buttons}\n'
            '</div></div>')


def _overlay_html(static: bool = False) -> str:
    if static:
        return ""
    return ('<div id="overlay"><div class="loader">\n'
            '  <div class="bars"><i></i><i></i><i></i><i></i><i></i></div>\n'
            '  <div class="msg">Fetching the latest data from BLS&hellip;</div>\n'
            '  <div class="sub">This can take up to a minute. '
            'The page will reload when done.</div>\n'
            '</div></div>')
```

- [ ] **Step 4: Add `static` param to `_toolbar_js`**

Change the signature and prepend a static branch. Replace
`def _toolbar_js() -> str:` (line 443) with:

```python
def _toolbar_js(static: bool = False) -> str:
    if static:
        return r"""
const $=id=>document.getElementById(id);
$("btn-pdf").addEventListener("click", ()=>window.print());
"""
```

Leave the existing `return r"""..."""` body below it unchanged (it becomes the
non-static path).

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_publish.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add dashboard/interactive_build.py tests/test_publish.py
git commit -m "feat: static-mode toolbar/JS helpers for the dashboard"
```

---

### Task 2: Thread `static` through `build_interactive`

Wire the new helpers into the page template so `build_interactive(static=True)`
emits the trimmed toolbar/overlay/JS.

**Files:**
- Modify: `dashboard/interactive_build.py` (signature line 129-130; template lines 258-269, 301)

- [ ] **Step 1: Add the param**

Change (lines 129-130):

```python
def build_interactive(cache_dir: Path = Path("data/cache"),
                      out_path: Path = Path("output/dashboard.html")) -> Path:
```

to:

```python
def build_interactive(cache_dir: Path = Path("data/cache"),
                      out_path: Path = Path("output/dashboard.html"),
                      static: bool = False) -> Path:
```

- [ ] **Step 2: Compute the markup before the template**

Just before `html = f"""<!DOCTYPE html>` (line 250), add:

```python
    toolbar_html = _toolbar_html(static)
    overlay_html = _overlay_html(static)
```

- [ ] **Step 3: Replace the inline toolbar block**

In the f-string, replace these lines (258-264):

```html
<div class="toolbar"><div class="wrap">
  <span class="brand">AI &amp; US jobs</span>
  <input id="bls-key" type="password" autocomplete="off" placeholder="BLS API key (optional; uses .env default)">
  <button id="btn-refresh" class="primary" title="Re-fetch the latest data from the BLS API">&#x21bb; Refresh from BLS</button>
  <button id="btn-pdf" title="Open the browser print dialog; choose Save as PDF">&#x2913; PDF</button>
  <button id="btn-xlsx" title="Download every chart's data, one sheet per chart">&#x2913; Data (Excel)</button>
</div></div>
```

with a single line:

```
{toolbar_html}
```

- [ ] **Step 4: Replace the inline overlay block**

Replace these lines (265-269):

```html
<div id="overlay"><div class="loader">
  <div class="bars"><i></i><i></i><i></i><i></i><i></i></div>
  <div class="msg">Fetching the latest data from BLS&hellip;</div>
  <div class="sub">This can take up to a minute. The page will reload when done.</div>
</div></div>
```

with a single line:

```
{overlay_html}
```

- [ ] **Step 5: Pass `static` to the JS emitter**

Change (line 301): `<script>{_toolbar_js()}</script>`
to: `<script>{_toolbar_js(static)}</script>`

- [ ] **Step 6: Manual build check (needs `data/cache`, which exists locally)**

Run (PowerShell):

```powershell
python -c "from pathlib import Path; from dashboard.interactive_build import build_interactive; p=build_interactive(out_path=Path('output/_static_check.html'), static=True); print(p)"
```

Expected: prints `output/_static_check.html`. Confirm trimmed toolbar:

Run: `python -c "t=open('output/_static_check.html',encoding='utf-8').read(); print('refresh', 'btn-refresh' in t); print('xlsx', 'id=\"btn-xlsx\"' in t); print('pdf', 'btn-pdf' in t)"`
Expected: `refresh False` / `xlsx False` / `pdf True`. Then delete the temp file.

- [ ] **Step 7: Run the full suite (regression)**

Run: `python -m pytest -q`
Expected: all green (existing 53 + 5 new).

- [ ] **Step 8: Commit**

```bash
git add dashboard/interactive_build.py
git commit -m "feat: static flag on build_interactive trims server-only UI"
```

---

### Task 3: `dashboard/publish.py`

One command that builds the static page straight to repo-root `index.html`.

**Files:**
- Create: `dashboard/publish.py`
- Test: `tests/test_publish.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_publish.py`:

```python
from pathlib import Path


def test_publish_delegates_static_to_root_index(monkeypatch):
    from dashboard import publish as pub
    calls = {}

    def fake_build(out_path, static):
        calls["out_path"] = Path(out_path)
        calls["static"] = static
        return Path(out_path)

    monkeypatch.setattr(pub, "build_interactive", fake_build)
    result = pub.publish()
    assert calls["static"] is True
    assert calls["out_path"] == Path("index.html")
    assert result == Path("index.html")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_publish.py::test_publish_delegates_static_to_root_index -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dashboard.publish'`

- [ ] **Step 3: Create the module**

Create `dashboard/publish.py`:

```python
"""Build the dashboard in static mode straight to repo-root index.html.

Run:  python -m dashboard.publish
Then commit index.html and push; GitHub Pages serves it from main/root.
"""
from __future__ import annotations

from pathlib import Path

from dashboard.interactive_build import build_interactive


def publish(out_path: Path = Path("index.html")) -> Path:
    return build_interactive(out_path=out_path, static=True)


if __name__ == "__main__":
    print(publish())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_publish.py::test_publish_delegates_static_to_root_index -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/publish.py tests/test_publish.py
git commit -m "feat: dashboard.publish builds static index.html"
```

---

### Task 4: Generate and commit the site files

**Files:**
- Create: `.nojekyll` (empty, repo root)
- Create: `index.html` (generated, repo root)

- [ ] **Step 1: Create `.nojekyll`**

Create an empty file at repo root named `.nojekyll` (no content). This stops
GitHub from running Jekyll over the static file.

- [ ] **Step 2: Build the published page**

Run: `python -m dashboard.publish`
Expected: prints `index.html`; file exists at repo root (~1.5MB).

- [ ] **Step 3: Verify it is the static build**

Run: `python -c "t=open('index.html',encoding='utf-8').read(); print('refresh', 'btn-refresh' in t); print('xlsx', 'id=\"btn-xlsx\"' in t); print('pdf', 'btn-pdf' in t)"`
Expected: `refresh False` / `xlsx False` / `pdf True`.

- [ ] **Step 4: Confirm files are not gitignored**

Run: `git check-ignore index.html .nojekyll`
Expected: no output (neither is ignored).

- [ ] **Step 5: Commit**

```bash
git add -f .nojekyll index.html
git commit -m "build: publish static dashboard as index.html for GitHub Pages"
```

---

### Task 5: README, merge to main, enable Pages, verify live

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add publish docs to README**

Add a section to `README.md` (near the existing dashboard build line):

```markdown
## Live site (GitHub Pages)

Published at: https://alanvaa06.github.io/unemployment_analysis/

Re-publish after a data refresh:

```bash
python -m dashboard.publish    # writes static index.html at repo root
git add index.html && git commit -m "build: refresh published dashboard" && git push
```

The published page is a snapshot. Live BLS refresh and Excel export remain in the
local app (`python app.py`).
```

- [ ] **Step 2: Commit the README**

```bash
git add README.md
git commit -m "docs: README section for the GitHub Pages site"
```

- [ ] **Step 3: Merge the branch to main**

Pages serves from `main`/root, so `index.html` must land on `main`.

```bash
git checkout main
git merge --no-ff feat/github-pages-publish -m "feat: publish dashboard to GitHub Pages"
git push origin main
```

- [ ] **Step 4: Enable GitHub Pages**

Try the API (confirm `gh` nested-field syntax; if it errors, use the dashed form
or the manual fallback):

```bash
gh api -X POST repos/alanvaa06/unemployment_analysis/pages \
  -f 'source[branch]=main' -f 'source[path]=/'
```

If the repo already has Pages configured, instead run:

```bash
gh api -X PUT repos/alanvaa06/unemployment_analysis/pages \
  -f 'source[branch]=main' -f 'source[path]=/'
```

Manual fallback: GitHub → Settings → Pages → Source = Deploy from a branch →
`main` / `/ (root)` → Save.

- [ ] **Step 5: Verify the live site**

Wait ~1-2 min for the first Pages build, then:

Run: `gh api repos/alanvaa06/unemployment_analysis/pages --jq '.html_url, .status'`
Expected: the URL and `built`.

Confirm it serves: fetch `https://alanvaa06.github.io/unemployment_analysis/`
and check the page title `Has AI taken a toll on jobs?` is present and the
toolbar shows only the PDF button.

- [ ] **Step 6: Update project logs**

Per `CLAUDE.md`: append one line to `docs/context/sesion-log.md`, add the
decision to `docs/context/memory.md`, and mark the todo done in
`docs/context/todo.md` if tracked. Commit:

```bash
git add docs/context/
git commit -m "docs: log GitHub Pages publish"
git push origin main
```

---

## Self-Review

- **Spec coverage:** static mode (Task 1-2), `publish.py` (Task 3), `.nojekyll` + committed `index.html` (Task 4), enable Pages + README + verify (Task 5). Data-freshness note → README Step 1. All spec sections covered.
- **Placeholders:** none — every code/command step is concrete.
- **Type consistency:** `_toolbar_html(static)`, `_overlay_html(static)`, `_toolbar_js(static)`, `build_interactive(..., static=False)`, `publish(out_path=Path("index.html"))` are consistent across tasks.
- **Risk:** the `gh` Pages nested-field flag form is unverified (Task 5 Step 4 carries a fallback). Build requires local `data/cache` (verified present).
