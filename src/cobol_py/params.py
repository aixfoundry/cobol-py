"""Parse / preprocess parameters.

Ports ``io.proleap.cobol.asg.params.CobolDialect`` and the
``CobolParserParams`` / ``CobolParserParamsImpl`` Java bean. The Java
interface + mutable implementation collapse to a single mutable dataclass —
callers read attributes directly (``params.format``) instead of getters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    copy_book_directories: List[Path] = field(default_factory=list)
    copy_book_extensions: List[str] = field(default_factory=list)
    copy_book_files: List[Path] = field(default_factory=list)
    dialect: Optional[CobolDialect] = None
    format: Optional[CobolSourceFormatEnum] = None
    ignore_syntax_errors: bool = False
