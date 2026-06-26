"""A single preprocessed COBOL source line and its line-type classification.

Ports ``io.proleap.cobol.preprocessor.sub.CobolLine`` and
``CobolLineTypeEnum``. ``CobolLine`` is intentionally a *mutable* class — it
forms a doubly-linked list (``predecessor`` / ``successor``) that the indicator
processor and line writer mutate in place to join continuation lines, exactly
as proleap does. Immutability is deliberately not applied here.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from ..params import CobolDialect
from .constants import CobolSourceFormatEnum, WS


class CobolLineTypeEnum(Enum):
    """Classification of a line derived from its indicator field character."""

    BLANK = "BLANK"
    COMMENT = "COMMENT"
    COMPILER_DIRECTIVE = "COMPILER_DIRECTIVE"
    CONTINUATION = "CONTINUATION"
    DEBUG = "DEBUG"
    NORMAL = "NORMAL"


class CobolLine:
    """One line of a COBOL source, split into its fixed-format areas.

    Each area has a current value plus an ``..._original`` snapshot taken when
    the line was first read; rewriters mutate the current values but the
    originals are retained for serialization of untouched regions.
    """

    # --- static factories / helpers (mirror the Java static methods) ---------

    @staticmethod
    def create_blank_sequence_area(format: CobolSourceFormatEnum) -> str:
        return "" if format in (CobolSourceFormatEnum.TANDEM, CobolSourceFormatEnum.FREE) else WS * 6

    @staticmethod
    def _extract_content_area_a(content_area: str) -> str:
        return content_area[:4] if len(content_area) > 4 else content_area

    @staticmethod
    def _extract_content_area_b(content_area: str) -> str:
        return content_area[4:] if len(content_area) > 4 else ""

    @classmethod
    def new_cobol_line(
        cls,
        sequence_area: str,
        indicator_area: str,
        content_area_a: str,
        content_area_b: str,
        comment_area: str,
        format: CobolSourceFormatEnum,
        dialect: CobolDialect,
        number: int,
        type: CobolLineTypeEnum,
    ) -> "CobolLine":
        # newCobolLine: originals == current values, no neighbours yet.
        return cls(
            sequence_area,
            sequence_area,
            indicator_area,
            indicator_area,
            content_area_a,
            content_area_a,
            content_area_b,
            content_area_b,
            comment_area,
            comment_area,
            format,
            dialect,
            number,
            type,
            None,
            None,
        )

    @classmethod
    def copy_with_content_area(cls, content_area: str, line: "CobolLine") -> "CobolLine":
        return cls(
            line.sequence_area,
            line.sequence_area_original,
            line.indicator_area,
            line.indicator_area_original,
            cls._extract_content_area_a(content_area),
            line.content_area_a_original,
            cls._extract_content_area_b(content_area),
            line.content_area_b_original,
            line.comment_area,
            line.comment_area_original,
            line.format,
            line.dialect,
            line.number,
            line.type,
            line.predecessor,
            line.successor,
        )

    @classmethod
    def copy_with_indicator_and_content_area(
        cls, indicator_area: str, content_area: str, line: "CobolLine"
    ) -> "CobolLine":
        return cls(
            line.sequence_area,
            line.sequence_area_original,
            indicator_area,
            line.indicator_area_original,
            cls._extract_content_area_a(content_area),
            line.content_area_a_original,
            cls._extract_content_area_b(content_area),
            line.content_area_b_original,
            line.comment_area,
            line.comment_area_original,
            line.format,
            line.dialect,
            line.number,
            line.type,
            line.predecessor,
            line.successor,
        )

    @classmethod
    def copy_with_indicator_area(
        cls, indicator_area: str, line: "CobolLine"
    ) -> "CobolLine":
        return cls(
            line.sequence_area,
            line.sequence_area_original,
            indicator_area,
            line.indicator_area_original,
            line.content_area_a,
            line.content_area_a_original,
            line.content_area_b,
            line.content_area_b_original,
            line.comment_area,
            line.comment_area_original,
            line.format,
            line.dialect,
            line.number,
            line.type,
            line.predecessor,
            line.successor,
        )

    # --- constructor ---------------------------------------------------------

    def __init__(
        self,
        sequence_area: str,
        sequence_area_original: str,
        indicator_area: str,
        indicator_area_original: str,
        content_area_a: str,
        content_area_a_original: str,
        content_area_b: str,
        content_area_b_original: str,
        comment_area: str,
        comment_area_original: str,
        format: CobolSourceFormatEnum,
        dialect: CobolDialect,
        number: int,
        type: CobolLineTypeEnum,
        predecessor: Optional["CobolLine"],
        successor: Optional["CobolLine"],
    ) -> None:
        self.sequence_area: str = sequence_area
        self.indicator_area: str = indicator_area
        self.content_area_a: str = content_area_a
        self.content_area_b: str = content_area_b
        self.comment_area: str = comment_area

        self.sequence_area_original: str = sequence_area_original
        self.indicator_area_original: str = indicator_area_original
        self.content_area_a_original: str = content_area_a_original
        self.content_area_b_original: str = content_area_b_original
        self.comment_area_original: str = comment_area_original

        self.format: CobolSourceFormatEnum = format
        self.dialect: CobolDialect = dialect
        self.number: int = number
        self.type: CobolLineTypeEnum = type

        self.predecessor: Optional[CobolLine] = None
        self.successor: Optional[CobolLine] = None
        self.set_predecessor(predecessor)
        self.set_successor(successor)

    # --- accessors -----------------------------------------------------------

    def get_blank_sequence_area(self) -> str:
        return self.create_blank_sequence_area(self.format)

    def get_comment_area(self) -> str:
        return self.comment_area

    def get_comment_area_original(self) -> str:
        return self.comment_area_original

    def get_content_area(self) -> str:
        return self.content_area_a + self.content_area_b

    def get_content_area_a(self) -> str:
        return self.content_area_a

    def get_content_area_a_original(self) -> str:
        return self.content_area_a_original

    def get_content_area_b(self) -> str:
        return self.content_area_b

    def get_content_area_b_original(self) -> str:
        return self.content_area_b_original

    def get_content_area_original(self) -> str:
        return self.content_area_a_original + self.content_area_b_original

    def get_dialect(self) -> CobolDialect:
        return self.dialect

    def get_format(self) -> CobolSourceFormatEnum:
        return self.format

    def get_indicator_area(self) -> str:
        return self.indicator_area

    def get_indicator_area_original(self) -> str:
        return self.indicator_area_original

    def get_number(self) -> int:
        return self.number

    def get_predecessor(self) -> Optional["CobolLine"]:
        return self.predecessor

    def get_sequence_area(self) -> str:
        return self.sequence_area

    def get_sequence_area_original(self) -> str:
        return self.sequence_area_original

    def get_successor(self) -> Optional["CobolLine"]:
        return self.successor

    def get_type(self) -> CobolLineTypeEnum:
        return self.type

    def serialize(self) -> str:
        return (
            self.sequence_area
            + self.indicator_area
            + self.content_area_a
            + self.content_area_b
            + self.comment_area
        )

    # --- doubly-linked list wiring ------------------------------------------

    def set_predecessor(self, predecessor: Optional["CobolLine"]) -> None:
        self.predecessor = predecessor
        if predecessor is not None:
            predecessor.successor = self

    def set_successor(self, successor: Optional["CobolLine"]) -> None:
        self.successor = successor
        if successor is not None:
            successor.predecessor = self

    def __str__(self) -> str:
        return self.serialize()
