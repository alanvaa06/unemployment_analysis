# Lessons

- Windows console is cp1252: printing emoji (✅/⚠️) to stdout crashes with UnicodeEncodeError. Reconfigure `sys.stdout`/`stderr` to utf-8 in CLI entrypoints; write report files with `encoding="utf-8"`.
- The Claude_in_Chrome `navigate` tool forces `https://` and mangles `file://` URLs. To preview a local HTML file, serve it (`python -m http.server --directory <dir>`) and navigate to `http://localhost:<port>/...`.
- CDP `Page.captureScreenshot` can time out on heavy pages (many Plotly charts + WebGL choropleth) even when the renderer is fine. Verify render state with a DOM query via `javascript_tool` (count `.main-svg`, `.geolayer`, traces) instead of relying on screenshots; settle the view before capturing.
- Scroll-reveal animations must be progressive enhancement: gate `opacity:0` under an `html.js` class (added by JS) and add a `setTimeout` fallback to reveal all. Otherwise content is invisible if JS/IntersectionObserver fails.
- BLS SA JOLTS components are seasonally adjusted independently, so `TS = QU+LD+OS` holds only approximately. Use a relative tolerance (~5%), not exact equality, in identity checks.
- BLS state-area (SAE) does not publish every metro × industry combo (e.g. some metro Information/PBS series). Treat "Series does not exist" as expected-missing, not a bug.
- AIOE uses 2010-SOC codes; OEWS/CPS current series use 2018-SOC. Detailed occupations like Software Developers (15-1252 in 2018) won't join AIOE directly. GPTs-are-GPTs (O*NET-SOC) joins better; use it as the primary exposure score.
