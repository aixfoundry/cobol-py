"""Interprets the indicator field of each line and joins continuations.

Ports ``io.proleap.cobol.preprocessor.sub.line.rewriter.impl.CobolLineIndicatorProcessorImpl``.

The continuation handling is the subtle part (four branches + fallback) and is
ported branch-for-branch from the Java source; see :meth:`process_line`.
"""

from __future__ import annotations

import re
from typing import List

from .constants import COMMENT_TAG, WS
from .line import CobolLine, CobolLineTypeEnum

# String-literal patterns used by _remove_string_literals, kept verbatim from
# the Java source. Built from quote characters to avoid quote-escaping noise.
_DQ = '"'
_SQ = "'"
_DOUBLE_QUOTE_LITERAL = re.compile(_DQ + r"([^" + _DQ + r"]|" + _DQ * 2 + r"|" + _SQ * 2 + r")*" + _DQ)
_SINGLE_QUOTE_LITERAL = re.compile(_SQ + r"([^" + _SQ + r"]|" + _SQ * 2 + r"|" + _DQ * 2 + r")*" + _SQ)

_LEADING_WS = re.compile(r"^\s+")
_TRAILING_WS = re.compile(r"\s+$")


class CobolLineIndicatorProcessorImpl:
    """Rewrites each line according to its indicator-field line type."""

    EMPTY_STRING = ""

    # --- public API ---------------------------------------------------------

    def process_lines(self, lines: List[CobolLine]) -> List[CobolLine]:
        return [self.process_line(line) for line in lines]

    def process_line(self, line: CobolLine) -> CobolLine:
        conditional_right_trimmed = self._conditional_right_trim_content_area(line)
        line_type = line.get_type()

        if line_type == CobolLineTypeEnum.DEBUG:
            return CobolLine.copy_with_indicator_and_content_area(
                WS, conditional_right_trimmed, line
            )

        if line_type == CobolLineTypeEnum.CONTINUATION:
            return self._process_continuation(line, conditional_right_trimmed)

        if line_type == CobolLineTypeEnum.COMMENT:
            return CobolLine.copy_with_indicator_and_content_area(
                COMMENT_TAG + WS, conditional_right_trimmed, line
            )

        if line_type == CobolLineTypeEnum.COMPILER_DIRECTIVE:
            return CobolLine.copy_with_indicator_and_content_area(
                WS, self.EMPTY_STRING, line
            )

        # NORMAL / default
        return CobolLine.copy_with_indicator_and_content_area(
            WS, conditional_right_trimmed, line
        )

    # --- continuation handling ----------------------------------------------

    def _process_continuation(
        self, line: CobolLine, content: str
    ) -> CobolLine:
        # Empty continuation -> blank indicator, empty content.
        if content is None or content == "":
            return CobolLine.copy_with_indicator_and_content_area(
                WS, self.EMPTY_STRING, line
            )

        predecessor = line.get_predecessor()

        # (2) Predecessor's *original* content ends with a quote char.
        if predecessor is not None and (
            predecessor.get_content_area_original().endswith(_DQ)
            or predecessor.get_content_area_original().endswith(_SQ)
        ):
            trimmed = self._trim_leading_whitespace(content)
            if trimmed.startswith(_DQ) or trimmed.startswith(_SQ):
                # ...continued line ended in a quote; remove the first quote.
                return CobolLine.copy_with_indicator_and_content_area(
                    WS, self._trim_leading_char(trimmed), line
                )
            # Non-compliant parser: just drop leading whitespace.
            return CobolLine.copy_with_indicator_and_content_area(
                WS, self._trim_leading_whitespace(content), line
            )

        # (3) Predecessor ends with an *open* literal.
        if predecessor is not None and self._is_ending_with_open_literal(predecessor):
            trimmed = self._trim_leading_whitespace(content)
            if trimmed.startswith(_DQ) or trimmed.startswith(_SQ):
                # Keep the literal open: drop the leading quote.
                return CobolLine.copy_with_indicator_and_content_area(
                    WS, self._trim_leading_char(trimmed), line
                )
            return CobolLine.copy_with_indicator_and_content_area(
                WS, content, line
            )

        # (4) Predecessor content ends with a quote (closed literal) -> prepend WS.
        if predecessor is not None and (
            predecessor.get_content_area().endswith(_DQ)
            or predecessor.get_content_area().endswith(_SQ)
        ):
            return CobolLine.copy_with_indicator_and_content_area(
                WS, WS + self._trim_leading_whitespace(content), line
            )

        # Fallback: trim leading whitespace.
        return CobolLine.copy_with_indicator_and_content_area(
            WS, self._trim_leading_whitespace(content), line
        )

    # --- helpers ------------------------------------------------------------

    def _conditional_right_trim_content_area(self, line: CobolLine) -> str:
        if not self._is_next_line_continuation(line):
            return self._right_trim_content_area(line.get_content_area())
        if not self._is_ending_with_open_literal(line):
            return self._right_trim_content_area(line.get_content_area())
        return line.get_content_area()

    def _is_next_line_continuation(self, line: CobolLine) -> bool:
        successor = line.get_successor()
        return (
            successor is not None
            and successor.get_type() == CobolLineTypeEnum.CONTINUATION
        )

    def _is_ending_with_open_literal(self, line: CobolLine) -> bool:
        content_area = line.get_content_area_original()
        without_literals = self._remove_string_literals(content_area)
        return _DQ in without_literals or _SQ in without_literals

    def _remove_string_literals(self, content_area: str) -> str:
        result = _DOUBLE_QUOTE_LITERAL.sub("", content_area)
        result = _SINGLE_QUOTE_LITERAL.sub("", result)
        return result

    def _repair_trailing_comma(self, content_area: str) -> str:
        if content_area == "":
            return content_area
        last_char = content_area[-1]
        if last_char == "," or last_char == ";":
            return content_area + WS
        return content_area

    def _right_trim_content_area(self, content_area: str) -> str:
        trimmed = self._trim_trailing_whitespace(content_area)
        return self._repair_trailing_comma(trimmed)

    @staticmethod
    def _trim_leading_char(content_area: str) -> str:
        return content_area[1:]

    @staticmethod
    def _trim_leading_whitespace(content_area: str) -> str:
        return _LEADING_WS.sub("", content_area)

    @staticmethod
    def _trim_trailing_whitespace(content_area: str) -> str:
        return _TRAILING_WS.sub("", content_area)
