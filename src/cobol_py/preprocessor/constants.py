"""Preprocessor constants and the COBOL source-format enum.

Ports the static constants and the nested ``CobolSourceFormatEnum`` from
``io.proleap.cobol.preprocessor.CobolPreprocessor``. The format regexes are
stored verbatim from the Java enum; the indicator-field class set is
``[ABCdD$<tab>\\-/*# ]``.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import List


# --- indicator / line-type single characters ---------------------------------

CHAR_ASTERISK = "*"
CHAR_D = "D"
CHAR_D_ = "d"
CHAR_DOLLAR_SIGN = "$"
CHAR_MINUS = "-"
CHAR_SLASH = "/"

# --- tags emitted / consumed by the preprocessor <-> main grammar round-trip -

COMMENT_ENTRY_TAG = "*>CE"
COMMENT_TAG = "*>"
EXEC_CICS_TAG = "*>EXECCICS"
EXEC_END_TAG = "}"
EXEC_SQL_TAG = "*>EXECSQL"
EXEC_SQLIMS_TAG = "*>EXECSQLIMS"

# --- whitespace / newline -----------------------------------------------------

WS = " "
NEWLINE = "\n"

# --- the indicator field character class -------------------------------------

# Some Japanese COBOL sources use full-width (ideographic) spaces (U+3000) in
# the indicator column.  Include it alongside the ASCII space.
# Also include letters E-Z used as non-standard indicator markers in the NIST
# COBOL85 test suite (treated as NORMAL lines).
INDICATOR_FIELD = r"([ABCDEFGHIJKLMNOPQRSTUVWXYZd$\t\-/*# 　])"


class CobolSourceFormatEnum(Enum):
    """COBOL source formats and their line-layout recognition regexes.

    Each member carries the verbatim regex used by the Java enum (matched with
    a full match, i.e. ``Matcher.matches()``) and the ``comment_entry_multi_line``
    flag that drives comment-entry marking.

    Capture groups (1-based), present for every format:

    1. sequence area
    2. indicator field
    3. content area A
    4. content area B
    5. comment area
    """

    FIXED = (r"(.{0,6})(?:" + INDICATOR_FIELD + r"(.{0,4})(.{0,61})(.*))?", True)
    TANDEM = (r"()(?:" + INDICATOR_FIELD + r"(.{0,4})(.*)())?", False)
    VARIABLE = (r"(.{0,6})(?:" + INDICATOR_FIELD + r"(.{0,4})(.*)())?", True)

    def __init__(self, regex: str, comment_entry_multi_line: bool) -> None:
        self.regex: str = regex
        # Java compiles eagerly in the enum constructor; do the same.
        self.pattern: re.Pattern[str] = re.compile(regex)
        self.comment_entry_multi_line: bool = comment_entry_multi_line


# Valid indicator-area characters for auto-detection heuristics.
# Mirrors INDICATOR_FIELD but as a plain set for membership tests.
_VALID_INDICATOR_SET = set("ABCDEFGHIJKLMNOPQRSTUVWXYZd$-\t/*# 　　　")  # letters A-Z, d, full-width spaces

# Sequence numbers in fixed-format COBOL are 6 characters: digits and spaces.
_SEQ_AREA_RE = re.compile(r"[0-9 ]{6}")


def detect_source_format(first_lines: List[str]) -> CobolSourceFormatEnum:
    """Auto-detect the COBOL source format from the first few lines of a file.

    *first_lines* should be text lines (already decoded, without trailing
    newlines or with them already stripped).

    Heuristic (evaluated for each line until one matches):

    1. **FIXED**: line length ≥ 7, columns 1-6 match ``[0-9 ]{6}`` (sequence
       area), and column 7 is in the standard indicator set.
    2. **TANDEM**: column 1 is in the standard indicator set.
    3. **Default**: :attr:`CobolSourceFormatEnum.FIXED`.

    Returns a :class:`CobolSourceFormatEnum` member.
    """
    for line in first_lines:
        stripped = line.rstrip("\n\r")
        if not stripped:
            continue
        # FIXED heuristic: 6-char sequence area + indicator at column 7.
        if len(stripped) >= 7:
            seq_area = stripped[:6]
            col7 = stripped[6]
            if _SEQ_AREA_RE.fullmatch(seq_area) and col7 in _VALID_INDICATOR_SET:
                return CobolSourceFormatEnum.FIXED
        # TANDEM heuristic: indicator at column 1.
        if stripped[0] in _VALID_INDICATOR_SET:
            return CobolSourceFormatEnum.TANDEM
    return CobolSourceFormatEnum.FIXED
