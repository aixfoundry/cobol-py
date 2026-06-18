"""cobol_py - a single-pass COBOL 85 parser built on a merged ANTLR4 grammar.

The generated ANTLR4 lexer / parser / listener / visitor modules live alongside
this file. Importing this package requires ``antlr4-python3-runtime`` (declared
in ``pyproject.toml``) because the generated modules do ``from antlr4 import *``.

Note: the ANTLR 4.13.2 Python target consolidates the old "base" classes, so
``Cobol85Listener`` already has empty enter/exit bodies (subclass and override)
and ``Cobol85Visitor`` returns ``visitChildren`` by default.
"""

from .Cobol85Lexer import Cobol85Lexer
from .Cobol85Parser import Cobol85Parser
from .Cobol85Listener import Cobol85Listener
from .Cobol85Visitor import Cobol85Visitor

__version__ = "0.1.0"

__all__ = [
    "Cobol85Lexer",
    "Cobol85Parser",
    "Cobol85Listener",
    "Cobol85Visitor",
    "__version__",
]
