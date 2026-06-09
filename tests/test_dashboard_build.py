"""Structural test for the pure HTML document assembler."""
from __future__ import annotations

from dashboard.build import Section, build_html_document


def test_build_html_document_structure() -> None:
    sections = [
        Section(id="ur", eyebrow="Exhibit 1", title="Unemployment rate",
                caption="A caption explaining the chart.",
                chart_html="<div id='chart-ur'></div>"),
        Section(id="edu", eyebrow="Exhibit 2", title="Education gradient",
                caption="Another caption.", chart_html="<div id='chart-edu'></div>"),
    ]
    kpis = {"Unemployment rate": "4.3%", "Bachelor's UR": "2.7%"}
    html = build_html_document(
        title="Has AI taken a toll on jobs?",
        subtitle="A BLS data view",
        kpis=kpis,
        sections=sections,
        asof="May 2026",
    )
    assert html.startswith("<!DOCTYPE html>")
    assert "Has AI taken a toll on jobs?" in html
    assert 'id="ur"' in html and 'id="edu"' in html
    assert "A caption explaining the chart." in html
    assert "chart-ur" in html
    assert "plotly" in html.lower()       # plotly.js loaded
    assert "4.3%" in html                  # KPI rendered
    assert "correlation" in html.lower()   # honesty caveat present
    assert "—" not in html                 # no em dashes (impeccable ban)
    # sticky nav links to both sections
    assert html.count("#ur") >= 1 and html.count("#edu") >= 1
