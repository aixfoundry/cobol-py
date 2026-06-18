"""cobol_py - a proleap-style COBOL parsing pipeline for Python.

Two ANTLR4 grammars drive the pipeline (matching proleap-cobol-parser):

* ``CobolPreprocessor.g4`` - recognises COPY / REPLACE / EXEC SQL-CICS-SQLIMS /
  compiler options; walked by the hand-written preprocessor to expand
  copybooks, apply replacements and extract EXEC blocks.
* ``Cobol.g4`` - the main COBOL grammar; parses the preprocessed text into an
  AST.

Typical use::

    from cobol_py import CobolParserRunner, CobolSourceFormatEnum

    ast = CobolParserRunner().parse_file("hello.cbl", CobolSourceFormatEnum.FIXED)

The generated ANTLR4 lexer / parser / listener / visitor modules live
alongside this file and require ``antlr4-python3-runtime`` (declared in
``pyproject.toml``).
"""

from __future__ import annotations

from .CobolLexer import CobolLexer
from .CobolListener import CobolListener
from .CobolParser import CobolParser
from .CobolPreprocessorLexer import CobolPreprocessorLexer
from .CobolPreprocessorListener import CobolPreprocessorListener
from .CobolPreprocessorParser import CobolPreprocessorParser
from .CobolPreprocessorVisitor import CobolPreprocessorVisitor
from .CobolVisitor import CobolVisitor
from .error_listener import ThrowingErrorListener
from .exceptions import CobolParserException, CobolPreprocessorException
from .params import CobolDialect, CobolParserParams
from .preprocessor.constants import CobolSourceFormatEnum
from .preprocessor.preprocessor import CobolPreprocessorImpl
from .runner import CobolParserRunner

__version__ = "0.1.0"

__all__ = [
    "CobolDialect",
    "CobolLexer",
    "CobolListener",
    "CobolParser",
    "CobolParserException",
    "CobolParserParams",
    "CobolParserRunner",
    "CobolPreprocessorException",
    "CobolPreprocessorImpl",
    "CobolPreprocessorLexer",
    "CobolPreprocessorListener",
    "CobolPreprocessorParser",
    "CobolPreprocessorVisitor",
    "CobolSourceFormatEnum",
    "CobolVisitor",
    "ThrowingErrorListener",
    "__version__",
]
