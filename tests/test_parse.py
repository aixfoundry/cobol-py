"""Round-trip parse tests for the merged Cobol85 grammar (Python target)."""

from __future__ import annotations

from pathlib import Path

import pytest
from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from cobol_py import Cobol85Lexer, Cobol85Parser

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class _CollectingErrorListener(ErrorListener):
    """Captures lexer/parser syntax errors instead of printing them."""

    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):  # noqa: N802
        self.errors.append(f"line {line}:{column} {msg}")


def parse(text: str):
    lexer = Cobol85Lexer(InputStream(text))
    parser = Cobol85Parser(CommonTokenStream(lexer))
    listener = _CollectingErrorListener()
    lexer.removeErrorListeners()
    parser.removeErrorListeners()
    lexer.addErrorListener(listener)
    parser.addErrorListener(listener)
    tree = parser.startRule()
    return tree, listener.errors


def test_parse_standard_program():
    # Regression: a plain COBOL 85 program with no preprocessor constructs must
    # still parse under the merged grammar.
    standard = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       PROCEDURE DIVISION.
           DISPLAY "Hello World".
           STOP RUN.
"""
    _tree, errors = parse(standard)
    assert errors == [], "standard program failed:\n" + "\n".join(errors)


def test_parse_merged_constructs():
    # Every merged-in preprocessor construct (compiler options, comment entries,
    # COPY, REPLACE, EXEC CICS/SQL, directives) must be recognized in one pass.
    text = (EXAMPLES / "example_merged.cbl").read_text()
    tree, errors = parse(text)
    assert errors == [], "example_merged.cbl failed:\n" + "\n".join(errors)
    # Sanity: the parse produced a startRule context.
    assert tree is not None
