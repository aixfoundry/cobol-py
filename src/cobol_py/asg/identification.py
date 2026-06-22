"""Identification division.

Ports ``metamodel/identification/{IdentificationDivision,ProgramIdParagraph}``
(interface + impl collapsed). The Program-ID paragraph carries the program
name; the optional author/date/... paragraphs are deferred.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Optional

from antlr4.ParserRuleContext import ParserRuleContext

from .base import CobolDivisionElement, NamedElement

if TYPE_CHECKING:
    from .program import ProgramUnit


class ProgramIdParagraph(CobolDivisionElement, NamedElement):
    """The PROGRAM-ID paragraph: program name plus an optional attribute."""

    class Attribute(Enum):
        COMMON = "COMMON"
        DEFINITION = "DEFINITION"
        INITIAL = "INITIAL"
        LIBRARY = "LIBRARY"
        RECURSIVE = "RECURSIVE"

    def __init__(
        self, name: Optional[str], program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]
    ) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name
        self.attribute: Optional["ProgramIdParagraph.Attribute"] = None


class IdentificationDivision(CobolDivisionElement):
    """IDENTIFICATION DIVISION."""

    def __init__(self, program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.program_id_paragraph: Optional[ProgramIdParagraph] = None
        # Optional paragraphs (author, date-written, ...) are deferred.

    def add_program_id_paragraph(self, ctx: ParserRuleContext) -> ProgramIdParagraph:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = ProgramIdParagraph(name, self.program_unit, ctx)
            self._set_attribute(result, ctx)
            self.program_id_paragraph = result
            self._register(result)
        return result

    @staticmethod
    def _set_attribute(paragraph: ProgramIdParagraph, ctx: ParserRuleContext) -> None:
        # Typed-token dispatch in Java's order (COMMON | INITIAL | LIBRARY |
        # DEFINITION | RECURSIVE). Avoids substring false-positives (a program
        # named "RECURSIVE-CALC" must not read as RECURSIVE) and the wrong
        # RECURSIVE-before-LIBRARY precedence of the old text scan.
        Attr = ProgramIdParagraph.Attribute

        def _present(token_name: str) -> bool:
            accessor = getattr(ctx, token_name, None)
            return callable(accessor) and accessor() is not None

        if _present("COMMON"):
            paragraph.attribute = Attr.COMMON
        elif _present("INITIAL"):
            paragraph.attribute = Attr.INITIAL
        elif _present("LIBRARY"):
            paragraph.attribute = Attr.LIBRARY
        elif _present("DEFINITION"):
            paragraph.attribute = Attr.DEFINITION
        elif _present("RECURSIVE"):
            paragraph.attribute = Attr.RECURSIVE
