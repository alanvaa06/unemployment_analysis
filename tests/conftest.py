"""Shared pytest fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Directory holding recorded BLS JSON and mini reference files."""
    return Path(__file__).parent / "fixtures"
