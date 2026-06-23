"""Parse / preprocess parameters.

Ports ``io.proleap.cobol.asg.params.CobolDialect`` and the
``CobolParserParams`` / ``CobolParserParamsImpl`` Java bean. The Java
interface + mutable implementation collapse to a single mutable dataclass —
callers read attributes directly (``params.format``) instead of getters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from .preprocessor.constants import CobolSourceFormatEnum


class CobolDialect(Enum):
    """COBOL dialect understood by the pipeline (mirrors the Java enum)."""

    ANSI85 = "ANSI85"
    MF = "MF"
    OSVS = "OSVS"


@dataclass
class CobolParserParams:
    """Parameters driving preprocessing and parsing.

    ``charset`` is a Python encoding name (e.g. ``"utf-8"``); the Java
    ``Charset`` object maps to the same concept. Copybook lookup fields use
    :class:`~pathlib.Path` in place of ``java.io.File``.
    """

    charset: str = "utf-8"
    # Copy-book lookup fields default to ``None`` (matching the Java bean's null
    # defaults), not empty lists: the finders branch on ``is not None``, so an
    # empty list would wrongly take the extension-matching path and never match.
    copy_book_directories: Optional[List[Path]] = None
    copy_book_extensions: Optional[List[str]] = None
    copy_book_files: Optional[List[Path]] = None
    dialect: Optional[CobolDialect] = None
    format: Optional[CobolSourceFormatEnum] = None
    ignore_missing_copy: bool = False
    """When True, missing copybooks are replaced with a comment line instead of
    raising :class:`CobolPreprocessorException`.  This lets the main grammar parse
    proceed for code that references unavailable copybooks.
    """
    ignore_syntax_errors: bool = False
