"""Marks comment-entry lines with the ``*>CE`` tag.

Ports ``io.proleap.cobol.preprocessor.sub.line.rewriter.impl.CobolCommentEntriesMarkerImpl``.

Comment entries follow identification-division trigger paragraphs (AUTHOR.,
INSTALLATION., ...). The marker escapes the trigger line (inserting the
``*>CE`` tag) and, for multi-line formats (FIXED/VARIABLE), continues tagging
subsequent area-B-only lines until a new paragraph/division begins. TANDEM is
single-line. Stateful: construct one instance per document.
"""

from __future__ import annotations

import re
from typing import List, Tuple

from ..params import CobolDialect
from .constants import COMMENT_ENTRY_TAG, WS
from .line import CobolLine, CobolLineTypeEnum

_TRIGGERS_END: Tuple[str, ...] = (
    "PROGRAM-ID.",
    "AUTHOR.",
    "INSTALLATION.",
    "DATE-WRITTEN.",
    "DATE-COMPILED.",
    "SECURITY.",
    "ENVIRONMENT",
    "DATA.",
    "PROCEDURE.",
)

_TRIGGERS_START: Tuple[str, ...] = (
    "AUTHOR.",
    "INSTALLATION.",
    "DATE-WRITTEN.",
    "DATE-COMPILED.",
    "SECURITY.",
    "REMARKS.",
)


class CobolCommentEntriesMarkerImpl:
    def __init__(self) -> None:
        # The Java regex leaves the trigger dots unescaped (``.`` == any char);
        # ported verbatim for behavioural parity.
        pattern = r"([ \t]*)(" + "|".join(_TRIGGERS_START) + r")(.+)"
        self._comment_entry_trigger_line_pattern = re.compile(pattern, re.IGNORECASE)
        # NOTE: the boolean state field is named distinctly from the
        # _is_in_comment_entry(...) method below; Java allows a field and method
        # of the same name to coexist, Python attribute lookup does not.
        self._found_comment_entry_trigger_in_previous_line = False
        self._currently_in_comment_entry = False

    # --- public API ---------------------------------------------------------

    def process_lines(self, lines: List[CobolLine]) -> List[CobolLine]:
        return [self.process_line(line) for line in lines]

    def process_line(self, line: CobolLine) -> CobolLine:
        if line.get_format().comment_entry_multi_line:
            return self._process_multi_line_comment_entry(line)
        return self._process_single_line_comment_entry(line)

    # --- multi-line (FIXED / VARIABLE) --------------------------------------

    def _process_multi_line_comment_entry(self, line: CobolLine) -> CobolLine:
        found_in_current = self._starts_with_trigger(line, _TRIGGERS_START)

        if found_in_current:
            result = self._escape_comment_entry(line)
        elif (
            self._found_comment_entry_trigger_in_previous_line
            or self._currently_in_comment_entry
        ):
            is_content_area_a_empty = line.get_content_area_a().strip() == ""
            is_in_osvs = self._is_in_osvs_comment_entry(line)
            self._currently_in_comment_entry = self._is_in_comment_entry(
                line, is_content_area_a_empty, is_in_osvs
            )
            if self._currently_in_comment_entry:
                result = self._build_multi_line_comment_entry_line(line)
            else:
                result = line
        else:
            result = line

        self._found_comment_entry_trigger_in_previous_line = found_in_current
        return result

    # --- single-line (TANDEM) -----------------------------------------------

    def _process_single_line_comment_entry(self, line: CobolLine) -> CobolLine:
        if self._starts_with_trigger(line, _TRIGGERS_START):
            return self._escape_comment_entry(line)
        return line

    # --- helpers ------------------------------------------------------------

    def _build_multi_line_comment_entry_line(self, line: CobolLine) -> CobolLine:
        return CobolLine.copy_with_indicator_area(
            COMMENT_ENTRY_TAG + WS, line
        )

    def _escape_comment_entry(self, line: CobolLine) -> CobolLine:
        matcher = self._comment_entry_trigger_line_pattern.fullmatch(
            line.get_content_area()
        )
        if matcher is None:
            return line
        whitespace = matcher.group(1)
        trigger = matcher.group(2)
        comment_entry = matcher.group(3)
        new_content_area = (
            whitespace + trigger + WS + COMMENT_ENTRY_TAG + comment_entry
        )
        return CobolLine.copy_with_content_area(new_content_area, line)

    def _is_in_comment_entry(
        self,
        line: CobolLine,
        is_content_area_a_empty: bool,
        is_in_osvs_comment_entry: bool,
    ) -> bool:
        return (
            line.get_type() == CobolLineTypeEnum.COMMENT
            or is_content_area_a_empty
            or is_in_osvs_comment_entry
        )

    def _is_in_osvs_comment_entry(self, line: CobolLine) -> bool:
        return (
            line.get_dialect() == CobolDialect.OSVS
            and not self._starts_with_trigger(line, _TRIGGERS_END)
        )

    @staticmethod
    def _starts_with_trigger(line: CobolLine, triggers: Tuple[str, ...]) -> bool:
        content_area_upper = line.get_content_area().upper().strip()
        return any(content_area_upper.startswith(trigger) for trigger in triggers)
