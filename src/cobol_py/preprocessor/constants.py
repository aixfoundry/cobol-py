"""Preprocessor constants and the COBOL source-format enum.

Ports the static constants and the nested ``CobolSourceFormatEnum`` from
``io.proleap.cobol.preprocessor.CobolPreprocessor``. The format regexes are
stored verbatim from the Java enum; the indicator-field class set is
``[ABCdD$<tab>\\-/*# ]``.
"""

from __future__ import annotations

import re
from enum import Enum


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

INDICATOR_FIELD = r"([ABCdD$\t\-/*# ])"


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
