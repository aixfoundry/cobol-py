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
        self.declaratives = None  # Declaratives (Phase later)
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

    # -- clauses (minimal stubs; internals that need createCall deferred) ----

    def add_declaratives(self, ctx: ParserRuleContext):
        if self.declaratives is None:
            self.declaratives = _ClauseStub(self.program_unit, ctx)
            self._register(self.declaratives)
        return self.declaratives

    def add_giving_clause(self, ctx: ParserRuleContext):
        if self.giving_clause is None:
            self.giving_clause = _ClauseStub(self.program_unit, ctx)
            self._register(self.giving_clause)
        return self.giving_clause

    def add_using_clause(self, ctx: ParserRuleContext):
        if self.using_clause is None:
            self.using_clause = _ClauseStub(self.program_unit, ctx)
            self._register(self.using_clause)
        return self.using_clause


class _ClauseStub(CobolDivisionElement):
    """Placeholder for declaratives / giving / using clauses.

    Their full structure (calls, parameters) depends on the ``createCall``
    machinery added in Phase C1; until then we only retain ``ctx`` and register
    the node so navigation still works.
    """
