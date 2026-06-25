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


def test_lang_toggle_es_highlights_es_and_links_en():
    h = ib._lang_toggle_html("es")
    assert 'href="en.html"' in h
    assert "ES" in h and "EN" in h
    assert "is-active" in h


def test_lang_toggle_en_highlights_en_and_links_es():
    h = ib._lang_toggle_html("en")
    assert 'href="index.html"' in h
    assert "is-active" in h


from pathlib import Path


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
