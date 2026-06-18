"""Reads raw COBOL text into a doubly-linked list of :class:`CobolLine`.

Ports ``io.proleap.cobol.preprocessor.sub.line.reader.impl.CobolLineReaderImpl``.
"""

from __future__ import annotations

import re
from typing import List

from ..exceptions import CobolPreprocessorException
from ..params import CobolParserParams
from .constants import (
    CHAR_ASTERISK,
    CHAR_D,
    CHAR_D_,
    CHAR_DOLLAR_SIGN,
    CHAR_MINUS,
    CHAR_SLASH,
    WS,
    CobolSourceFormatEnum,
)
from .line import CobolLine, CobolLineTypeEnum

_LINE_SEPARATOR = re.compile(r"\r\n|\r|\n")


def _split_lines(text: str) -> List[str]:
    """Split *text* into lines the way Java ``Scanner.nextLine()`` does.

    Java's line scanner (like ``BufferedReader.readLine()``) does **not** emit
    a trailing empty line for a single terminating separator, but plain
    :func:`re.split` would. We split on ``\\r\\n|\\r|\\n`` (the same separator
    set Java uses — not the wider Unicode boundaries of ``str.splitlines``)
    and drop exactly one trailing empty field produced by a terminal
    separator. An empty input yields zero lines.
    """
    if text == "":
        return []
    parts = _LINE_SEPARATOR.split(text)
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


_FORMAT_DESCRIPTIONS = {
    CobolSourceFormatEnum.FIXED: (
        "Columns 1-6 sequence number, column 7 indicator area, "
        "columns 8-72 for areas A and B"
    ),
    CobolSourceFormatEnum.TANDEM: (
        "Column 1 indicator area, columns 2 and all following for areas A and B"
    ),
    CobolSourceFormatEnum.VARIABLE: (
        "Columns 1-6 sequence number, column 7 indicator area, "
        "columns 8 and all following for areas A and B"
    ),
}


class CobolLineReaderImpl:
    """Splits raw text into ``CobolLine`` objects and classifies each line."""

    @staticmethod
    def _determine_type(indicator_area: str) -> CobolLineTypeEnum:
        if indicator_area in (CHAR_D, CHAR_D_):
            return CobolLineTypeEnum.DEBUG
        if indicator_area == CHAR_MINUS:
            return CobolLineTypeEnum.CONTINUATION
        if indicator_area in (CHAR_ASTERISK, CHAR_SLASH):
            return CobolLineTypeEnum.COMMENT
        if indicator_area == CHAR_DOLLAR_SIGN:
            return CobolLineTypeEnum.COMPILER_DIRECTIVE
        # WS or anything else -> NORMAL (Java: WS falls through to default)
        return CobolLineTypeEnum.NORMAL

    def parse_line(
        self, line: str, line_number: int, params: CobolParserParams
    ) -> CobolLine:
        fmt = params.format
        matcher = fmt.pattern.fullmatch(line)

        if matcher is None:
            description = _FORMAT_DESCRIPTIONS.get(fmt, "")
            message = (
                f"Is {params.format} the correct line format ({description})? "
                f"Could not parse line {line_number + 1}: {line}"
            )
            raise CobolPreprocessorException(message)

        # Capture groups: 1 seq, 2 indicator, 3 area A, 4 area B, 5 comment.
        sequence_area = matcher.group(1) or ""
        indicator_area = matcher.group(2)
        if indicator_area is None:
            indicator_area = WS
        content_area_a = matcher.group(3) or ""
        content_area_b = matcher.group(4) or ""
        comment_area = matcher.group(5) or ""

        line_type = self._determine_type(indicator_area)

        return CobolLine.new_cobol_line(
            sequence_area,
            indicator_area,
            content_area_a,
            content_area_b,
            comment_area,
            params.format,
            params.dialect,
            line_number,
            line_type,
        )

    def process_lines(
        self, lines: str, params: CobolParserParams
    ) -> List[CobolLine]:
        result: List[CobolLine] = []
        last_cobol_line: CobolLine | None = None
        line_number = 0

        for current_line in _split_lines(lines):
            current_cobol_line = self.parse_line(current_line, line_number, params)
            current_cobol_line.set_predecessor(last_cobol_line)
            result.append(current_cobol_line)
            line_number += 1
            last_cobol_line = current_cobol_line

        return result
