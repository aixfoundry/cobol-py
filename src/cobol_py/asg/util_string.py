"""Small string->value helpers (port of ``asg/util/AsgStringUtils``)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional


def parse_decimal(text: Optional[str]) -> Optional[Decimal]:
    """Parse a COBOL numeric literal text into :class:`Decimal` (None if unable)."""
    if text is None:
        return None
    cleaned = text.strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None
