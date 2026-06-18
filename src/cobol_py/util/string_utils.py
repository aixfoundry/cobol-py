"""General string helpers.

Ports ``io.proleap.cobol.asg.util.StringUtils``. Only the small set of helpers
used by the parsing pipeline (currently :func:`capitalize`, used by the runner
when deriving a program identifier from a file name) is exercised; the rest are
ported verbatim for parity with proleap.
"""

from __future__ import annotations

from typing import Optional


def capitalize(s: Optional[str]) -> Optional[str]:
    if s is None or s == "":
        return s
    return s[0].upper() + s[1:]


def count_matches(s: str, target: str) -> int:
    return (len(s) - len(s.replace(target, ""))) // len(target)


def left_pad(s: str, size: int, pad_char: str = " ") -> str:
    pads = max(0, size - len(s))
    return pad_char * pads + s


def lowercase_first_letter(data: str) -> str:
    first_letter = data[0].lower()
    rest_letters = data[1:]
    return first_letter + rest_letters


def right_pad(s: str, size: int, pad_char: str = " ") -> str:
    pads = max(0, size - len(s))
    return s + pad_char * pads


def substring_after(s: str, separator: str) -> str:
    pos = s.find(separator)
    return "" if pos == -1 else s[pos + len(separator):]


def substring_before(s: str, separator: str) -> str:
    pos = s.find(separator)
    return s if pos == -1 else s[:pos]
