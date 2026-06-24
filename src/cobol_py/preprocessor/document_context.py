"""Preprocessor output buffer + active replacement mappings.

Ports ``io.proleap.cobol.preprocessor.sub.document.impl.CobolDocumentContext``.
"""

from __future__ import annotations

from typing import List, Optional

from .replacement_mapping import CobolReplacementMapping


class CobolDocumentContext:
    """Accumulates preprocessed text and applies REPLACE mappings to it."""

    def __init__(self) -> None:
        self._current_replaceable_replacements: Optional[List[CobolReplacementMapping]] = None
        self._output_buffer: list[str] = []
        self._prefix: Optional[str] = None

    def store_prefix(self, prefix: Optional[str]) -> None:
        """Store the PREFIXING/PREFIX value for the current copybook expansion."""
        self._prefix = prefix

    def get_prefix(self) -> Optional[str]:
        """Return the current PREFIXING/PREFIX value, or *None*."""
        return self._prefix

    def read(self) -> str:
        return "".join(self._output_buffer)

    def write(self, text: str) -> None:
        self._output_buffer.append(text)

    def store_replaceables_and_replacements(self, replace_clauses) -> None:
        if replace_clauses is None:
            self._current_replaceable_replacements = None
            return

        mappings: List[CobolReplacementMapping] = []
        for replace_clause in replace_clauses:
            mapping = CobolReplacementMapping()
            mapping.replaceable = replace_clause.replaceable()
            mapping.replacement = replace_clause.replacement()
            mappings.append(mapping)
        self._current_replaceable_replacements = mappings

    def replace_replaceables_by_replacements(self, tokens) -> None:
        if self._current_replaceable_replacements is None:
            return

        # Longest replaceable first (see CobolReplacementMapping.__lt__).
        for mapping in sorted(self._current_replaceable_replacements):
            current_output = self.read()
            replaced_output = mapping.replace(current_output, tokens)
            self._output_buffer = [replaced_output]
