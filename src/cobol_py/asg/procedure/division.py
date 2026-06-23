"""Procedure division structure: scopes, statements, sections, paragraphs.

Ports ``metamodel/procedure/{ProcedureDivision,Section,Paragraph,ParagraphName,
Statement,StatementTypeEnum}`` and the structural core of ``metamodel/impl/
ScopeImpl`` (interface + impl collapsed into one class per concept). ``Scope``
is the shared base for ProcedureDivision / Section / Paragraph and owns the
statements list; the per-verb ``add_<verb>_statement(ctx)`` factories are added
in Phase C1.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

from antlr4.ParserRuleContext import ParserRuleContext

from ..base import CobolDivisionElement, Declaration

if TYPE_CHECKING:
    from ..program import ProgramUnit


def _symbol(name: Optional[str]) -> Optional[str]:
    """Upper-case symbol-table key (mirrors ``ProgramUnitElementImpl.getSymbol``)."""
    if name is None or name == "":
        return name
    return name.upper()


class StatementTypeEnum(Enum):
    """Every COBOL verb (mirrors ``procedure.StatementTypeEnum``)."""

    ACCEPT = "ACCEPT"
    ADD = "ADD"
    ALTER = "ALTER"
    CALL = "CALL"
    CANCEL = "CANCEL"
    CLOSE = "CLOSE"
    COMPUTE = "COMPUTE"
    CONTINUE = "CONTINUE"
    DECLARATIVES = "DECLARATIVES"
    DELETE = "DELETE"
    DISABLE = "DISABLE"
    DISPLAY = "DISPLAY"
    DIVIDE = "DIVIDE"
    ENABLE = "ENABLE"
    ENTRY = "ENTRY"
    EVALUATE = "EVALUATE"
    EXEC_CICS = "EXEC_CICS"
    EXEC_SQL = "EXEC_SQL"
    EXEC_SQLIMS = "EXEC_SQLIMS"
    EXHIBIT = "EXHIBIT"
    EXIT = "EXIT"
    GENERATE = "GENERATE"
    GO_BACK = "GO_BACK"
    GO_TO = "GO_TO"
    IF = "IF"
    INITIALIZE = "INITIALIZE"
    INITIATE = "INITIATE"
    INSPECT = "INSPECT"
    MERGE = "MERGE"
    MOVE = "MOVE"
    MULTIPLY = "MULTIPLY"
    OPEN = "OPEN"
    PERFORM = "PERFORM"
    PURGE = "PURGE"
    READ = "READ"
    RECEIVE = "RECEIVE"
    RELEASE = "RELEASE"
    RETURN = "RETURN"
    REWRITE = "REWRITE"
    SEARCH = "SEARCH"
    SEND = "SEND"
    SET = "SET"
    SORT = "SORT"
    START = "START"
    STOP = "STOP"
    STRING = "STRING"
    SUBTRACT = "SUBTRACT"
    TERMINATE = "TERMINATE"
    UNSTRING = "UNSTRING"
    USE = "USE"
    WRITE = "WRITE"


class Statement(CobolDivisionElement):
    """Base for all COBOL procedure statements.

    Concrete statements (Phase C1) set ``statement_type``. ``scope`` is the
    enclosing ProcedureDivision / Section / Paragraph.
    """

    statement_type: Optional[StatementTypeEnum] = None

    def __init__(
        self,
        program_unit: "ProgramUnit",
        scope: "Scope",
        ctx: Optional[ParserRuleContext],
    ) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.scope = scope


class ParagraphName(CobolDivisionElement, Declaration):
    """A paragraph name declaration."""

    def __init__(
        self, name: Optional[str], program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]
    ) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name


class Scope(CobolDivisionElement):
    """A statement container: ProcedureDivision, Section, or Paragraph.

    Owns the ordered ``statements`` list. ``register_statement`` appends a built
    statement and registers it (mirrors ``ScopeImpl.registerStatement``); the
    per-verb factories that call it arrive in Phase C1.
    """

    def __init__(self, program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.statements: List[Statement] = []

    def register_statement(self, statement: Statement) -> None:
        self.statements.append(statement)
        self._register(statement)


class Paragraph(Scope, Declaration):
    """A paragraph: a named scope within a section or the procedure division."""

    def __init__(
        self, name: Optional[str], program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]
    ) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name
        self.paragraph_name: Optional[ParagraphName] = None
        self.section: Optional["Section"] = None
        self.calls: List = []  # ProcedureCall (Phase C1/F)

    def add_paragraph_name(self, paragraph_name: ParagraphName) -> None:
        self.paragraph_name = paragraph_name

    def add_call(self, procedure_call) -> None:  # Phase C1/F
        self.calls.append(procedure_call)


class Section(Scope, Declaration):
    """A named section within the procedure division; contains paragraphs."""

    def __init__(
        self, name: Optional[str], program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]
    ) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name
        self.calls: List = []  # SectionCall (Phase C1/F)
        self._paragraphs: List[Paragraph] = []
        self._paragraphs_by_name: Dict[Optional[str], List[Paragraph]] = {}

    def add_call(self, section_call) -> None:  # Phase C1/F
        self.calls.append(section_call)

    def add_paragraph(self, ctx: ParserRuleContext) -> Paragraph:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = Paragraph(name, self.program_unit, ctx)
            result.section = self
            self._register_paragraph(result)
            # Sections also register their paragraphs with the procedure
            # division (mirrors SectionImpl.addParagraph).
            pd = self.program_unit.procedure_division
            if pd is not None:
                pd._register_paragraph(result)
            paragraph_name = self.add_paragraph_name(ctx.paragraphName())
            result.add_paragraph_name(paragraph_name)
            self._register(result)
        return result  # type: ignore[return-value]

    def add_paragraph_name(self, ctx: ParserRuleContext) -> ParagraphName:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = ParagraphName(name, self.program_unit, ctx)
            self._register(result)
        return result  # type: ignore[return-value]

    def _register_paragraph(self, paragraph: Paragraph) -> None:
        self._paragraphs.append(paragraph)
        self._paragraphs_by_name.setdefault(_symbol(paragraph.name), []).append(paragraph)

    @property
    def paragraphs(self) -> List[Paragraph]:
        return self._paragraphs

    def get_paragraph(self, name: str) -> Optional[Paragraph]:
        entries = self._paragraphs_by_name.get(_symbol(name), [])
        return entries[0] if entries else None


class ProcedureDivision(Scope):
    """The PROCEDURE DIVISION: sections, paragraphs, and their statements."""

    def __init__(self, program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.declaratives: Optional["Declaratives"] = None  # built by add_declaratives
        self.giving_clause = None  # GivingClause
        self.using_clause = None  # UsingClause
        self._sections: List[Section] = []
        self._paragraphs: List[Paragraph] = []
        self._sections_by_name: Dict[Optional[str], List[Section]] = {}
        self._paragraphs_by_name: Dict[Optional[str], List[Paragraph]] = {}

    # -- sections ------------------------------------------------------------

    def add_section(self, ctx: ParserRuleContext) -> Section:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = Section(name, self.program_unit, ctx)
            self._sections.append(result)
            self._sections_by_name.setdefault(_symbol(name), []).append(result)
            self._register(result)
        return result

    @property
    def sections(self) -> List[Section]:
        return self._sections

    def get_section(self, name: str) -> Optional[Section]:
        entries = self._sections_by_name.get(_symbol(name), [])
        return entries[0] if entries else None

    # -- paragraphs ----------------------------------------------------------

    def add_paragraph_name(self, ctx: ParserRuleContext) -> ParagraphName:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = ParagraphName(name, self.program_unit, ctx)
            self._register(result)
        return result

    def add_paragraph(self, ctx: ParserRuleContext) -> Paragraph:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = Paragraph(name, self.program_unit, ctx)
            self._register_paragraph(result)
            paragraph_name = self.add_paragraph_name(ctx.paragraphName())
            result.add_paragraph_name(paragraph_name)
            self._register(result)
        return result

    def _register_paragraph(self, paragraph: Paragraph) -> None:
        self._paragraphs.append(paragraph)
        self._paragraphs_by_name.setdefault(_symbol(paragraph.name), []).append(paragraph)

    @property
    def paragraphs(self) -> List[Paragraph]:
        """Every paragraph, including ones nested in sections."""
        return self._paragraphs

    @property
    def root_paragraphs(self) -> List[Paragraph]:
        """Paragraphs not nested in a section."""
        return [p for p in self._paragraphs if p.section is None]

    def get_paragraph(self, name: str) -> Optional[Paragraph]:
        entries = self._paragraphs_by_name.get(_symbol(name), [])
        return entries[0] if entries else None

    # -- clauses (using / giving / declaratives) ---------------------------

    def add_declaratives(self, ctx: ParserRuleContext) -> "Optional[Declaratives]":
        result = self._get_element(ctx)
        if result is None:
            result = Declaratives(self.program_unit, ctx)
            self.declaratives = result
            self._register(result)
            # declaratives
            for declarative_ctx in ctx.procedureDeclarative():
                result.add_declarative(declarative_ctx)
        return result  # type: ignore[return-value]

    def add_giving_clause(self, ctx: ParserRuleContext):
        result = self._get_element(ctx)
        if result is None:
            result = GivingClause(self.program_unit, ctx)
            # grammar: (GIVING | RETURNING) dataName
            data_name = ctx.dataName()
            if data_name is not None:
                result.giving_call = self.create_call(data_name)
            self.giving_clause = result
            self._register(result)
        return result

    def add_using_clause(self, ctx: ParserRuleContext):
        result = self._get_element(ctx)
        if result is None:
            result = UsingClause(self.program_unit, ctx)
            for param_ctx in ctx.procedureDivisionUsingParameter():
                param = result.add_using_parameter(param_ctx)
            self.using_clause = result
            self._register(result)
        return result


# --- Procedure Division clause models -------------------------------------

class UsingParameterType(Enum):
    REFERENCE = "REFERENCE"
    VALUE = "VALUE"


class ByReference(CobolDivisionElement):
    """A single ``BY REFERENCE`` data item: ``[OPTIONAL] identifier|fileName | ANY``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.reference_call = None
        self.optional = False
        self.any = False


class ByValue(CobolDivisionElement):
    """A single ``BY VALUE`` item: ``identifier | literal | ANY``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.value_value_stmt = None
        self.any = False


class ByReferencePhrase(CobolDivisionElement):
    """``(BY? REFERENCE)? byReference+``: a group of BY REFERENCE parameters."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.by_references: List[ByReference] = []

    def add_by_reference(self, ctx: ParserRuleContext) -> ByReference:
        result = self._get_element(ctx)
        if result is None:
            result = ByReference(self.program_unit, ctx)
            if ctx.OPTIONAL() is not None:
                result.optional = True
            if ctx.ANY() is not None:
                result.any = True
            result.reference_call = self.create_call(
                ctx.identifier() or ctx.fileName()
            )
            self.by_references.append(result)
            self._register(result)
        return result


class ByValuePhrase(CobolDivisionElement):
    """``BY? VALUE byValue+``: a group of BY VALUE parameters."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.by_values: List[ByValue] = []

    def add_by_value(self, ctx: ParserRuleContext) -> ByValue:
        result = self._get_element(ctx)
        if result is None:
            result = ByValue(self.program_unit, ctx)
            if ctx.ANY() is not None:
                result.any = True
            result.value_value_stmt = self.create_value_stmt(
                ctx.identifier(), ctx.literal()
            )
            self.by_values.append(result)
            self._register(result)
        return result


class UsingParameter(CobolDivisionElement):
    """One USING parameter: either ``BY REFERENCE`` or ``BY VALUE`` phrase."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.using_parameter_type: Optional[UsingParameterType] = None
        self.by_reference_phrase: Optional[ByReferencePhrase] = None
        self.by_value_phrase: Optional[ByValuePhrase] = None


class UsingClause(CobolDivisionElement):
    """``USING|CHAINING usingParameter+``: the USING clause of PROCEDURE DIVISION."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.using_parameters: List[UsingParameter] = []

    def add_using_parameter(self, ctx: ParserRuleContext) -> UsingParameter:
        result = self._get_element(ctx)
        if result is None:
            result = UsingParameter(self.program_unit, ctx)
            # Determine phrase type: BY REFERENCE or BY VALUE
            ref_phrase_ctx = ctx.procedureDivisionByReferencePhrase()
            val_phrase_ctx = ctx.procedureDivisionByValuePhrase()
            if ref_phrase_ctx is not None:
                result.using_parameter_type = UsingParameterType.REFERENCE
                phrase = ByReferencePhrase(self.program_unit, ref_phrase_ctx)
                for ref_ctx in ref_phrase_ctx.procedureDivisionByReference():
                    phrase.add_by_reference(ref_ctx)
                self._register(phrase)
                result.by_reference_phrase = phrase
            elif val_phrase_ctx is not None:
                result.using_parameter_type = UsingParameterType.VALUE
                phrase = ByValuePhrase(self.program_unit, val_phrase_ctx)
                for val_ctx in val_phrase_ctx.procedureDivisionByValue():
                    phrase.add_by_value(val_ctx)
                self._register(phrase)
                result.by_value_phrase = phrase
            self.using_parameters.append(result)
            self._register(result)
        return result


class GivingClause(CobolDivisionElement):
    """``GIVING|RETURNING dataName``: the GIVING clause of PROCEDURE DIVISION."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.giving_call = None


# --- Declaratives block -----------------------------------------------------
#
# Ports ``metamodel/procedure/declaratives/{Declaratives,Declarative,
# SectionHeader}`` (interface + impl collapsed into one class per concept).
# Grammar::
#
#   procedureDeclaratives  : DECLARATIVES DOT_FS procedureDeclarative+
#                             END DECLARATIVES DOT_FS
#   procedureDeclarative   : procedureSectionHeader DOT_FS useStatement
#                             DOT_FS paragraphs
#   procedureSectionHeader : sectionName SECTION integerLiteral?


class SectionHeader(CobolDivisionElement):
    """The section header that opens a declarative (``sectionName SECTION ...``).

    Ports ``procedure.declaratives.SectionHeader``: a marker element. It is
    distinct from :class:`Section`, which is a named scope owning paragraphs.
    """


class Declarative(CobolDivisionElement):
    """One declarative: a section header plus a USE statement (+ its paragraphs).

    Ports ``procedure.declaratives.Declarative``.
    """

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.section_header: Optional[SectionHeader] = None
        self.use_statement = None  # UseStatement

    def add_section_header(self, ctx: Optional[ParserRuleContext]) -> Optional[SectionHeader]:
        if ctx is None:
            return None
        result = self._get_element(ctx)
        if result is None:
            result = SectionHeader(self.program_unit, ctx)
            self.section_header = result
            self._register(result)
        return result

    def add_use_statement(self, ctx: Optional[ParserRuleContext]):
        if ctx is None:
            return None
        from .statements import UseStatement

        result = self._get_element(ctx)
        if result is None:
            # Mirrors DeclarativeImpl.addUseStatement: the USE statement scopes
            # back to the procedure division, but is owned by this declarative
            # (it is NOT appended to procedure_division.statements).
            procedure_division = self.program_unit.procedure_division
            result = UseStatement(self.program_unit, procedure_division, ctx)
            result._populate()
            self.use_statement = result
            self._register(result)
        return result


class Declaratives(CobolDivisionElement):
    """The DECLARATIVES block: a container of declarative sections.

    Ports ``procedure.declaratives.Declaratives``.
    """

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.declaratives: List[Declarative] = []

    def add_declarative(self, ctx: ParserRuleContext) -> Declarative:
        result = self._get_element(ctx)
        if result is None:
            result = Declarative(self.program_unit, ctx)
            result.add_section_header(ctx.procedureSectionHeader())
            result.add_use_statement(ctx.useStatement())
            self.declaratives.append(result)
            self._register(result)
        return result
