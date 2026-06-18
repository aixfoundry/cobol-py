"""Exception types raised by the COBOL preprocessor and parser.

Ports ``io.proleap.cobol.preprocessor.exception.CobolPreprocessorException`` and
``io.proleap.cobol.asg.exception.CobolParserException``.
"""

from __future__ import annotations


class CobolPreprocessorException(RuntimeError):
    """Raised when the preprocessor cannot transform a COBOL source."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CobolParserException(RuntimeError):
    """Raised on a fatal COBOL parse (syntax) error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
