"""Shared fixtures and helpers for the cobol-py test-suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from cobol_py.params import CobolParserParams
from cobol_py.preprocessor.constants import CobolSourceFormatEnum

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Directory holding the ``.cbl`` / ``.CPY`` fixture sources."""
    return FIXTURES


def fixed_params(*, copy_book_directories: list[Path] | None = None) -> CobolParserParams:
    """FIXED-format params, optionally pointing COPY at a copybook directory."""
    return CobolParserParams(
        format=CobolSourceFormatEnum.FIXED,
        copy_book_directories=copy_book_directories,
    )
