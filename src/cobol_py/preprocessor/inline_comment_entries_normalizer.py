"""Normalizes ``*>`` inline comment tags to ``*> `` (tag + space).

Ports ``io.proleap.cobol.preprocessor.sub.line.rewriter.impl.CobolInlineCommentEntriesNormalizerImpl``.
"""

from __future__ import annotations

import re
from typing import List

from .constants import COMMENT_TAG, WS
from .line import CobolLine

# ``*>`` immediately followed by a non-space character marks a denormalized
# inline comment tag that needs a trailing space inserted.
_DENORMALIZED_COMMENT_ENTRY = re.compile(r"\*>[^ ]")


class CobolInlineCommentEntriesNormalizerImpl:
    def process_line(self, line: CobolLine) -> CobolLine:
        if not _DENORMALIZED_COMMENT_ENTRY.search(line.get_content_area()):
            return line
        new_content_area = line.get_content_area().replace(
            COMMENT_TAG, COMMENT_TAG + WS
        )
        return CobolLine.copy_with_content_area(new_content_area, line)

    def process_lines(self, lines: List[CobolLine]) -> List[CobolLine]:
        return [self.process_line(line) for line in lines]
