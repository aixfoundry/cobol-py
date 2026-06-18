"""Serializes processed ``CobolLine`` objects back to text.

Ports ``io.proleap.cobol.preprocessor.sub.line.writer.impl.CobolLineWriterImpl``.
Continuation lines are joined onto the previous line's content (no newline, no
indicator / sequence area), which is what realizes COBOL line continuation.
"""

from __future__ import annotations

from typing import List

from .constants import NEWLINE
from .line import CobolLine, CobolLineTypeEnum


class CobolLineWriterImpl:
    def serialize(self, lines: List[CobolLine]) -> str:
        out: list[str] = []
        for line in lines:
            not_continuation = line.get_type() != CobolLineTypeEnum.CONTINUATION
            if not_continuation:
                if line.get_number() > 0:
                    out.append(NEWLINE)
                out.append(line.get_blank_sequence_area())
                out.append(line.get_indicator_area())
            out.append(line.get_content_area())
        return "".join(out)
