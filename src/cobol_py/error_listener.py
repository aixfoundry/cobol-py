"""An ANTLR4 error listener that raises on syntax errors.

Ports ``io.proleap.cobol.asg.runner.ThrowingErrorListener`` — every lexer/parser
syntax error is converted into a :class:`~cobol_py.exceptions.CobolParserException`
instead of being printed to stderr.
"""

from __future__ import annotations

from antlr4.error.ErrorListener import ErrorListener

from .exceptions import CobolParserException


class ThrowingErrorListener(ErrorListener):
    """Converts every syntax error into a :class:`CobolParserException`."""

    def syntaxError(  # noqa: N802 - mirrors the ANTLR4 Java method name
        self,
        recognizer,
        offendingSymbol,
        line,
        column,
        msg,
        e,
    ) -> None:
        raise CobolParserException(f"syntax error in line {line}:{column} {msg}")
