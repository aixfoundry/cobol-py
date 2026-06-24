"""COBOL preprocessor orchestration: read -> rewrite -> parse document.

Ports ``io.proleap.cobol.preprocessor.impl.CobolPreprocessorImpl``.

Pipeline: raw COBOL -> :class:`CobolLineReader` -> indicator processor /
inline-comment normalizer / comment-entries marker -> :class:`CobolLineWriter`
serialization -> :class:`CobolDocumentParser` (COPY / REPLACE / EXEC expansion).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Union

from ..params import CobolParserParams
from .comment_entries_marker import CobolCommentEntriesMarkerImpl
from .document_parser import CobolDocumentParserImpl
from .inline_comment_entries_normalizer import CobolInlineCommentEntriesNormalizerImpl
from .line import CobolLine
from .line_indicator_processor import CobolLineIndicatorProcessorImpl
from .line_reader import CobolLineReaderImpl
from .line_writer import CobolLineWriterImpl

_LOG = logging.getLogger(__name__)

# Module-level cache for preprocessed copybook content.
# Key: (file_path_str, charset, format_name).  Value: preprocessed text.
# Shared across all CobolPreprocessorImpl instances within a process.
# In a multiprocessing batch, each worker builds its own cache independently.
_COPYBOOK_CACHE: dict[tuple, str] = {}


class CobolPreprocessorImpl:
    """The proleap preprocessor: text-in, preprocessed-text-out."""

    # --- component factories (mirror the Java create* methods) --------------

    @staticmethod
    def _create_comment_entries_marker() -> CobolCommentEntriesMarkerImpl:
        return CobolCommentEntriesMarkerImpl()

    @staticmethod
    def _create_document_parser() -> CobolDocumentParserImpl:
        return CobolDocumentParserImpl()

    @staticmethod
    def _create_inline_comment_entries_normalizer() -> CobolInlineCommentEntriesNormalizerImpl:
        return CobolInlineCommentEntriesNormalizerImpl()

    @staticmethod
    def _create_line_indicator_processor() -> CobolLineIndicatorProcessorImpl:
        return CobolLineIndicatorProcessorImpl()

    @staticmethod
    def _create_line_reader() -> CobolLineReaderImpl:
        return CobolLineReaderImpl()

    @staticmethod
    def _create_line_writer() -> CobolLineWriterImpl:
        return CobolLineWriterImpl()

    # --- public API ---------------------------------------------------------

    def process(self, cobol_code: str, params: CobolParserParams) -> str:
        lines = self._read_lines(cobol_code, params)
        rewritten_lines = self._rewrite_lines(lines)
        return self._parse_document(rewritten_lines, params)

    def process_file(
        self, cobol_file: Union[str, Path], params: CobolParserParams
    ) -> str:
        charset = params.charset
        cobol_file = Path(cobol_file)

        # Check the module-level cache.  Many copybooks are shared across
        # hundreds of main files; preprocessing each one once per worker
        # process saves the ANTLR4 lex/parse/walk overhead on every reuse.
        cache_key = (str(cobol_file), charset)
        cached = _COPYBOOK_CACHE.get(cache_key)
        if cached is not None:
            return cached

        _LOG.info(
            "Preprocessing file %s with line format %s and charset %s.",
            cobol_file.name,
            params.format,
            charset,
        )
        try:
            cobol_file_content = cobol_file.read_text(encoding=charset)
        except UnicodeDecodeError:
            # The file may be in a different encoding than the parent
            # (e.g. a cp932 copybook included from a euc-jp main file).
            # Fall back through common Japanese encodings.
            raw = cobol_file.read_bytes()
            _CANDIDATES = ("euc-jp", "cp932", "utf-8", "latin-1")
            for fallback in _CANDIDATES:
                if fallback == charset:
                    continue
                try:
                    cobol_file_content = raw.decode(fallback)
                    charset = fallback
                    params.charset = fallback  # cascade to nested copybooks
                    _LOG.info(
                        "Fallback: reading %s as %s (parent charset was %s).",
                        cobol_file.name,
                        fallback,
                        params.charset if charset != fallback else charset,
                    )
                    # Re-check cache with the resolved charset.
                    cache_key = (str(cobol_file), charset)
                    cached = _COPYBOOK_CACHE.get(cache_key)
                    if cached is not None:
                        return cached
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # Last resort: latin-1 decodes every byte.
                cobol_file_content = raw.decode("latin-1")
                charset = "latin-1"
                params.charset = "latin-1"

        result = self.process(cobol_file_content, params)
        _COPYBOOK_CACHE[cache_key] = result
        return result

    # --- pipeline steps -----------------------------------------------------

    def _read_lines(
        self, cobol_code: str, params: CobolParserParams
    ) -> List[CobolLine]:
        return self._create_line_reader().process_lines(cobol_code, params)

    def _rewrite_lines(self, lines: List[CobolLine]) -> List[CobolLine]:
        line_indicator_processed = self._create_line_indicator_processor().process_lines(lines)
        normalized_inline_comment_entries = (
            self._create_inline_comment_entries_normalizer().process_lines(
                line_indicator_processed
            )
        )
        return self._create_comment_entries_marker().process_lines(
            normalized_inline_comment_entries
        )

    def _parse_document(
        self, lines: List[CobolLine], params: CobolParserParams
    ) -> str:
        code = self._create_line_writer().serialize(lines)
        return self._create_document_parser().process_lines(code, params)
