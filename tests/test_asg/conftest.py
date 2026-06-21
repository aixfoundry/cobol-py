"""Shared fixtures for ASG tests."""

from __future__ import annotations

import pytest
from cobol_py import CobolParserRunner, CobolSourceFormatEnum
from cobol_py.params import CobolParserParams


@pytest.fixture
def analyze():
    """Return a callable that analyzes a COBOL source string into a Program."""

    def _analyze(src: str):
        params = CobolParserParams(format=CobolSourceFormatEnum.FIXED)
        return CobolParserRunner().analyze(src, params)

    return _analyze
