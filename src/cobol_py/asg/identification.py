"""Identification division.

Ports ``metamodel/identification/`` — all 7 identification paragraphs
(Program-ID, Author, Date-Written, Date-Compiled, Installation, Remarks,
Security) plus the IdentificationDivision container. Java interface + Impl
pairs are collapsed into single Python classes.
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


class AuthorParagraph(CobolDivisionElement):
    """AUTHOR paragraph: name of the person who wrote the program."""

    def __init__(self, program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.author: Optional[str] = None


class DateWrittenParagraph(CobolDivisionElement):
    """DATE-WRITTEN paragraph: date the program was written."""

    def __init__(self, program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.date_written: Optional[str] = None


class DateCompiledParagraph(CobolDivisionElement):
    """DATE-COMPILED paragraph: date the program was compiled."""

    def __init__(self, program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.date_compiled: Optional[str] = None


class InstallationParagraph(CobolDivisionElement):
    """INSTALLATION paragraph: site where the program will be used."""

    def __init__(self, program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.installation: Optional[str] = None


class RemarksParagraph(CobolDivisionElement):
    """REMARKS paragraph: describes the function of the program."""

    def __init__(self, program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.remarks: Optional[str] = None


class SecurityParagraph(CobolDivisionElement):
    """SECURITY paragraph: security restrictions for the program."""

    def __init__(self, program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.security: Optional[str] = None


class IdentificationDivision(CobolDivisionElement):
    """IDENTIFICATION DIVISION."""

    def __init__(self, program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.program_id_paragraph: Optional[ProgramIdParagraph] = None
        self.author_paragraph: Optional[AuthorParagraph] = None
        self.date_written_paragraph: Optional[DateWrittenParagraph] = None
        self.date_compiled_paragraph: Optional[DateCompiledParagraph] = None
        self.installation_paragraph: Optional[InstallationParagraph] = None
        self.remarks_paragraph: Optional[RemarksParagraph] = None
        self.security_paragraph: Optional[SecurityParagraph] = None

    def add_program_id_paragraph(self, ctx: ParserRuleContext) -> ProgramIdParagraph:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = ProgramIdParagraph(name, self.program_unit, ctx)
            self._set_attribute(result, ctx)
            self.program_id_paragraph = result
            self._register(result)
        return result

    def add_author_paragraph(self, ctx: ParserRuleContext) -> AuthorParagraph:
        result = self._get_element(ctx)
        if result is None:
            result = AuthorParagraph(self.program_unit, ctx)
            result.author = _body_text(ctx)
            self.author_paragraph = result
            self._register(result)
        return result

    def add_date_written_paragraph(self, ctx: ParserRuleContext) -> DateWrittenParagraph:
        result = self._get_element(ctx)
        if result is None:
            result = DateWrittenParagraph(self.program_unit, ctx)
            result.date_written = _body_text(ctx)
            self.date_written_paragraph = result
            self._register(result)
        return result

    def add_date_compiled_paragraph(self, ctx: ParserRuleContext) -> DateCompiledParagraph:
        result = self._get_element(ctx)
        if result is None:
            result = DateCompiledParagraph(self.program_unit, ctx)
            result.date_compiled = _body_text(ctx)
            self.date_compiled_paragraph = result
            self._register(result)
        return result

    def add_installation_paragraph(self, ctx: ParserRuleContext) -> InstallationParagraph:
        result = self._get_element(ctx)
        if result is None:
            result = InstallationParagraph(self.program_unit, ctx)
            result.installation = _body_text(ctx)
            self.installation_paragraph = result
            self._register(result)
        return result

    def add_remarks_paragraph(self, ctx: ParserRuleContext) -> RemarksParagraph:
        result = self._get_element(ctx)
        if result is None:
            result = RemarksParagraph(self.program_unit, ctx)
            result.remarks = _body_text(ctx)
            self.remarks_paragraph = result
            self._register(result)
        return result

    def add_security_paragraph(self, ctx: ParserRuleContext) -> SecurityParagraph:
        result = self._get_element(ctx)
        if result is None:
            result = SecurityParagraph(self.program_unit, ctx)
            result.security = _body_text(ctx)
            self.security_paragraph = result
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


def _body_text(ctx: ParserRuleContext) -> str:
    """Extract paragraph body text, stripping the keyword heading.

    The ANTLR context contains the full paragraph text including the keyword
    (e.g. "AUTHOR. John Doe."). We extract the part after the period.
    """
    raw = ctx.getText() if ctx else ""
    # Find the first period (keyword separator) and return what follows
    idx = raw.find(".")
    if idx >= 0:
        return raw[idx + 1:].strip()
    return raw.strip()
