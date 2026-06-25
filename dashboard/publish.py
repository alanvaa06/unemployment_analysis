"""Build the dashboard in static mode for both languages, ready for GitHub Pages.

Run:  python -m dashboard.publish
Writes index.html (Spanish, default) and en.html (English) at the repo root.
Then commit both and push; GitHub Pages serves them from main/root.
"""
from __future__ import annotations

from pathlib import Path

from dashboard.interactive_build import build_interactive


def publish(es_path: Path = Path("index.html"),
            en_path: Path = Path("en.html")) -> list[Path]:
    return [
        build_interactive(out_path=es_path, static=True, lang="es"),
        build_interactive(out_path=en_path, static=True, lang="en"),
    ]


if __name__ == "__main__":
    for p in publish():
        print(p)
