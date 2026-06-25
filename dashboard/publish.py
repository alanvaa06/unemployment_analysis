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
