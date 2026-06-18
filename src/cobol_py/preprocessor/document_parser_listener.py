"""ANTLR listener that expands COPY / applies REPLACE / extracts EXEC blocks.

Ports ``io.proleap.cobol.preprocessor.sub.document.impl.CobolDocumentParserListenerImpl``.

The listener maintains a stack of :class:`CobolDocumentContext` buffers. On
entering a COPY / REPLACE / EXEC / compiler-option region it pushes a fresh
context (so that region's terminals are captured separately); on exit it pops,
transforms, and writes the result into the enclosing context. ``visitTerminal``
writes hidden tokens + terminal text into the current context.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

from cobol_py.CobolPreprocessorListener import CobolPreprocessorListener

from ..exceptions import CobolPreprocessorException
from ..params import CobolParserParams
from .constants import (
    EXEC_CICS_TAG,
    EXEC_END_TAG,
    EXEC_SQLIMS_TAG,
    EXEC_SQL_TAG,
    NEWLINE,
    WS,
)
from .copybook import (
    CobolWordCopyBookFinderImpl,
    FilenameCopyBookFinderImpl,
    LiteralCopyBookFinderImpl,
)
from .document_context import CobolDocumentContext
from .line import CobolLine
from .line_reader import _split_lines
from .token_utils import (
    get_hidden_tokens_to_left,
    get_text_including_hidden_tokens,
    is_eof,
)

_LOG = logging.getLogger(__name__)

# "(?i)(end-exec)" in the Java source - case-insensitive, captured so it can be
# echoed back into the replacement followed by the EXEC_END_TAG.
_END_EXEC_PATTERN = re.compile(r"(end-exec)", re.IGNORECASE)


class CobolDocumentParserListenerImpl(CobolPreprocessorListener):
    def __init__(self, params: CobolParserParams, tokens) -> None:
        self._params = params
        self._tokens = tokens
        self._contexts: List[CobolDocumentContext] = [CobolDocumentContext()]

    # --- context stack ------------------------------------------------------

    def context(self) -> CobolDocumentContext:
        return self._contexts[-1]

    def _push(self) -> CobolDocumentContext:
        ctx = CobolDocumentContext()
        self._contexts.append(ctx)
        return ctx

    def _pop(self) -> CobolDocumentContext:
        return self._contexts.pop()

    # --- finder factories (mirror the Java create* methods) -----------------

    @staticmethod
    def _create_cobol_word_copy_book_finder() -> CobolWordCopyBookFinderImpl:
        return CobolWordCopyBookFinderImpl()

    @staticmethod
    def _create_filename_copy_book_finder() -> FilenameCopyBookFinderImpl:
        return FilenameCopyBookFinderImpl()

    @staticmethod
    def _create_literal_copy_book_finder() -> LiteralCopyBookFinderImpl:
        return LiteralCopyBookFinderImpl()

    # --- enter rules: push a fresh context ----------------------------------

    def enterCompilerOptions(self, ctx) -> None:
        self._push()

    def enterCopyStatement(self, ctx) -> None:
        self._push()

    def enterEjectStatement(self, ctx) -> None:
        self._push()

    def enterExecCicsStatement(self, ctx) -> None:
        self._push()

    def enterExecSqlImsStatement(self, ctx) -> None:
        self._push()

    def enterExecSqlStatement(self, ctx) -> None:
        self._push()

    def enterReplaceArea(self, ctx) -> None:
        self._push()

    def enterReplaceByStatement(self, ctx) -> None:
        self._push()

    def enterReplaceOffStatement(self, ctx) -> None:
        self._push()

    def enterSkipStatement(self, ctx) -> None:
        self._push()

    def enterTitleStatement(self, ctx) -> None:
        self._push()

    # --- exit rules: pop, transform, write into parent ----------------------

    def exitCompilerOptions(self, ctx) -> None:
        # throw away COMPILER OPTIONS terminals
        self._pop()

    def exitEjectStatement(self, ctx) -> None:
        self._pop()

    def exitReplaceByStatement(self, ctx) -> None:
        self._pop()

    def exitReplaceOffStatement(self, ctx) -> None:
        self._pop()

    def exitSkipStatement(self, ctx) -> None:
        self._pop()

    def exitTitleStatement(self, ctx) -> None:
        self._pop()

    def exitCopyStatement(self, ctx) -> None:
        # throw away COPY terminals
        self._pop()

        # a new context for the copy book content
        self._push()

        # replacement phrase
        for replacing_phrase in ctx.replacingPhrase():
            self.context().store_replaceables_and_replacements(replacing_phrase.replaceClause())

        # copy the copy book
        copy_source = ctx.copySource()
        copy_book_content = self._get_copy_book_content(copy_source, self._params)

        if copy_book_content is not None:
            self.context().write(copy_book_content + NEWLINE)
            self.context().replace_replaceables_by_replacements(self._tokens)

        content = self.context().read()
        self._pop()

        self.context().write(content)

    def exitExecCicsStatement(self, ctx) -> None:
        self._exit_exec_statement(ctx, EXEC_CICS_TAG)

    def exitExecSqlImsStatement(self, ctx) -> None:
        self._exit_exec_statement(ctx, EXEC_SQLIMS_TAG)

    def exitExecSqlStatement(self, ctx) -> None:
        self._exit_exec_statement(ctx, EXEC_SQL_TAG)

    def _exit_exec_statement(self, ctx, tag: str) -> None:
        # throw away EXEC ... terminals
        self._pop()

        # a new context for the statement
        self._push()

        text = get_text_including_hidden_tokens(ctx, self._tokens)
        line_prefix = CobolLine.create_blank_sequence_area(self._params.format) + tag
        lines = self._build_lines(text, line_prefix)

        self.context().write(lines)

        content = self.context().read()
        self._pop()

        self.context().write(content)

    def exitReplaceArea(self, ctx) -> None:
        replace_clauses = ctx.replaceByStatement().replaceClause()
        self.context().store_replaceables_and_replacements(replace_clauses)

        self.context().replace_replaceables_by_replacements(self._tokens)
        content = self.context().read()

        self._pop()
        self.context().write(content)

    # --- terminal visitor ---------------------------------------------------

    def visitTerminal(self, node) -> None:  # noqa: N802 - ANTLR callback name
        tok_pos = node.getSourceInterval()[0]
        self.context().write(get_hidden_tokens_to_left(tok_pos, self._tokens))

        if not is_eof(node):
            self.context().write(node.getText())

    # --- helpers ------------------------------------------------------------

    def _build_lines(self, text: str, line_prefix: str) -> str:
        out: list[str] = []
        first_line = True

        for line in _split_lines(text):
            if not first_line:
                out.append(NEWLINE)

            trimmed_line = line.strip()
            prefixed_line = line_prefix + WS + trimmed_line
            # ReplaceBuilder: echo the matched "end-exec" then a space + EXEC_END_TAG.
            suffixed_line = _END_EXEC_PATTERN.sub(
                lambda m: m.group(1) + WS + EXEC_END_TAG, prefixed_line
            )

            out.append(suffixed_line)
            first_line = False

        return "".join(out)

    def _find_copy_book(self, copy_source, params: CobolParserParams):
        if copy_source.cobolWord() is not None:
            return self._create_cobol_word_copy_book_finder().find_copy_book(
                params, copy_source.cobolWord()
            )
        if copy_source.literal() is not None:
            return self._create_literal_copy_book_finder().find_copy_book(
                params, copy_source.literal()
            )
        if copy_source.filename() is not None:
            return self._create_filename_copy_book_finder().find_copy_book(
                params, copy_source.filename()
            )
        _LOG.warning("unknown copy book reference type %s", copy_source)
        return None

    def _get_copy_book_content(self, copy_source, params: CobolParserParams):
        copy_book = self._find_copy_book(copy_source, params)

        if copy_book is None:
            raise CobolPreprocessorException(
                "Could not find copy book "
                + copy_source.getText()
                + " in directory of COBOL input file or copy books param object."
            )

        try:
            # Deferred import: CobolPreprocessorImpl (orchestration) depends on
            # the document parser, which depends on this listener.
            from .preprocessor import CobolPreprocessorImpl

            return CobolPreprocessorImpl().process_file(copy_book, params)
        except OSError as e:
            _LOG.warning("%s", e)
            return None
