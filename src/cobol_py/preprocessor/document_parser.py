"""Parses cleaned COBOL text with the preprocessor grammar and walks it.

Ports ``io.proleap.cobol.preprocessor.sub.document.impl.CobolDocumentParserImpl``.

A trigger guard skips the (expensive) lex/parse/walk when the source contains
none of the recognised preprocessor constructs; otherwise the text is parsed
with ``CobolPreprocessor.g4`` and walked by the document listener, which
performs COPY / REPLACE / EXEC expansion.
"""

from __future__ import annotations

from typing import Tuple

from antlr4 import CommonTokenStream, InputStream
from antlr4.tree.Tree import ParseTreeWalker

from cobol_py.CobolPreprocessorLexer import CobolPreprocessorLexer
from cobol_py.CobolPreprocessorParser import CobolPreprocessorParser

from ..error_listener import ThrowingErrorListener
from ..params import CobolParserParams
from .document_parser_listener import CobolDocumentParserListenerImpl

_TRIGGERS: Tuple[str, ...] = (
    "cbl",
    "copy",
    "exec sql",
    "exec sqlims",
    "exec cics",
    "process",
    "replace",
    "eject",
    "skip1",
    "skip2",
    "skip3",
    "title",
)


class CobolDocumentParserImpl:
    """Parses and processes COPY / REPLACE / EXEC SQL statements."""

    @staticmethod
    def _contains_trigger(code: str) -> bool:
        code_lower = code.lower()
        return any(trigger in code_lower for trigger in _TRIGGERS)

    def _create_document_parser_listener(self, params, tokens):
        return CobolDocumentParserListenerImpl(params, tokens)

    def process_lines(self, code: str, params: CobolParserParams) -> str:
        if self._contains_trigger(code):
            return self._process_with_parser(code, params)
        return code

    def _process_with_parser(self, code: str, params: CobolParserParams) -> str:
        # run the lexer
        lexer = CobolPreprocessorLexer(InputStream(code))

        if not params.ignore_syntax_errors:
            # register an error listener, so that preprocessing stops on errors
            lexer.removeErrorListeners()
            lexer.addErrorListener(ThrowingErrorListener())

        # get a list of matched tokens
        tokens = CommonTokenStream(lexer)

        # pass the tokens to the parser
        parser = CobolPreprocessorParser(tokens)

        if not params.ignore_syntax_errors:
            parser.removeErrorListeners()
            parser.addErrorListener(ThrowingErrorListener())

        # specify our entry point
        start_rule = parser.startRule()

        # analyze contained copy books
        listener = self._create_document_parser_listener(params, tokens)
        ParseTreeWalker.DEFAULT.walk(listener, start_rule)

        return listener.context().read()
