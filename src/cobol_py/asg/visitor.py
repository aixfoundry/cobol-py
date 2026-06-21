"""ASG build visitors.

Ports ``asg/visitor/impl``. Each visitor subclasses the generated
:class:`cobol_py.CobolVisitor` (which provides ``visit``/``visitChildren``),
overrides the relevant ``visitXxx(ctx)``, locates its enclosing ASG scope via
:func:`cobol_py.asg.antlr_utils.find_parent`, calls the matching ``add_*``
factory, then recurses via ``visitChildren``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from antlr4.tree.Tree import ParseTree

from ..CobolVisitor import CobolVisitor
from . import antlr_utils
from .program import CompilationUnit, Program, ProgramUnit

if TYPE_CHECKING:
    from .procedure.division import ProcedureDivision, Scope


class AbstractCobolParserVisitor(CobolVisitor):
    """Base for ASG visitors: holds the :class:`Program` and offers navigation."""

    def __init__(self, program: Program) -> None:
        self.program = program

    def _find(self, asg_type, ctx: ParseTree):  # type: ignore[no-untyped-def]
        return antlr_utils.find_parent(asg_type, ctx, self.program.registry)

    def find_compilation_unit(self, ctx: ParseTree) -> Optional[CompilationUnit]:
        return self._find(CompilationUnit, ctx)

    def find_program_unit(self, ctx: ParseTree) -> Optional[ProgramUnit]:
        return self._find(ProgramUnit, ctx)

    def find_scope(self, ctx: ParseTree) -> "Optional[Scope]":
        from .procedure.division import Scope

        return self._find(Scope, ctx)

    def find_procedure_division(self, ctx: ParseTree) -> "Optional[ProcedureDivision]":
        from .procedure.division import ProcedureDivision

        return self._find(ProcedureDivision, ctx)

    def get_element(self, ctx: ParseTree):
        return self.program.registry.get(ctx)


class CobolCompilationUnitVisitor(AbstractCobolParserVisitor):
    """Pass 0 (during parse): create the :class:`CompilationUnit`."""

    def __init__(
        self,
        compilation_unit_name: str,
        lines: List[str],
        tokens,
        program: Program,
    ) -> None:
        super().__init__(program)
        self.compilation_unit_name = compilation_unit_name
        self.lines = lines
        self.tokens = tokens

    def visitCompilationUnit(self, ctx):  # noqa: N802 - ANTLR callback
        compilation_unit = CompilationUnit(
            self.compilation_unit_name, self.program, self.tokens, ctx
        )
        compilation_unit.lines = self.lines
        return self.visitChildren(ctx)


class CobolProgramUnitVisitor(AbstractCobolParserVisitor):
    """Pass 1: create ProgramUnits and the four divisions."""

    def __init__(self, compilation_unit: CompilationUnit) -> None:
        super().__init__(compilation_unit.program)
        self.compilation_unit = compilation_unit

    def visitProgramUnit(self, ctx):  # noqa: N802
        self.compilation_unit.add_program_unit(ctx)
        return self.visitChildren(ctx)

    def visitIdentificationDivision(self, ctx):  # noqa: N802
        program_unit = self.find_program_unit(ctx)
        if program_unit is not None:
            program_unit.add_identification_division(ctx)
        return self.visitChildren(ctx)

    def visitEnvironmentDivision(self, ctx):  # noqa: N802
        program_unit = self.find_program_unit(ctx)
        if program_unit is not None:
            program_unit.add_environment_division(ctx)
        return self.visitChildren(ctx)

    def visitDataDivision(self, ctx):  # noqa: N802
        program_unit = self.find_program_unit(ctx)
        if program_unit is not None:
            program_unit.add_data_division(ctx)
        return self.visitChildren(ctx)

    def visitProcedureDivision(self, ctx):  # noqa: N802
        program_unit = self.find_program_unit(ctx)
        if program_unit is not None:
            program_unit.add_procedure_division(ctx)
        return self.visitChildren(ctx)


class CobolProcedureDivisionVisitor(AbstractCobolParserVisitor):
    """Pass 2: build procedure-division structure (sections, paragraphs, clauses).

    Ports ``CobolProcedureDivisionVisitorImpl``. Statement bodies are populated
    by the statement-dispatch visitor in Phase C1.
    """

    def visitParagraph(self, ctx):  # noqa: N802
        from .procedure.division import ProcedureDivision, Section

        scope = self.find_scope(ctx)
        if isinstance(scope, (ProcedureDivision, Section)):
            scope.add_paragraph(ctx)
        return self.visitChildren(ctx)

    def visitParagraphName(self, ctx):  # noqa: N802
        procedure_division = self.find_procedure_division(ctx)
        if procedure_division is not None:
            procedure_division.add_paragraph_name(ctx)
        return self.visitChildren(ctx)

    def visitProcedureDeclaratives(self, ctx):  # noqa: N802
        procedure_division = self.find_procedure_division(ctx)
        if procedure_division is not None:
            procedure_division.add_declaratives(ctx)
        return self.visitChildren(ctx)

    def visitProcedureDivisionGivingClause(self, ctx):  # noqa: N802
        procedure_division = self.find_procedure_division(ctx)
        if procedure_division is not None:
            procedure_division.add_giving_clause(ctx)
        return self.visitChildren(ctx)

    def visitProcedureDivisionUsingClause(self, ctx):  # noqa: N802
        procedure_division = self.find_procedure_division(ctx)
        if procedure_division is not None:
            procedure_division.add_using_clause(ctx)
        return self.visitChildren(ctx)

    def visitProcedureSection(self, ctx):  # noqa: N802
        procedure_division = self.find_procedure_division(ctx)
        if procedure_division is not None:
            procedure_division.add_section(ctx)
        return self.visitChildren(ctx)


class CobolProcedureStatementVisitor(AbstractCobolParserVisitor):
    """Pass 3: build typed statement nodes for the core verbs (Phase C1).

    Ports ``CobolProcedureStatementVisitorImpl``. Each ``visit<Verb>Statement``
    finds the enclosing scope and calls ``StmtClass.build``; recursion via
    ``visitChildren`` also attaches statements nested inside IF / PERFORM inline
    to their enclosing scope.
    """

    def _build(self, stmt_cls, ctx):
        scope = self.find_scope(ctx)
        if scope is not None:
            stmt_cls.build(scope, ctx)
        return self.visitChildren(ctx)

    def visitAcceptStatement(self, ctx):  # noqa: N802
        from .procedure.statements import AcceptStatement

        return self._build(AcceptStatement, ctx)

    def visitAddStatement(self, ctx):  # noqa: N802
        from .procedure.statements import AddStatement

        return self._build(AddStatement, ctx)

    def visitSubtractStatement(self, ctx):  # noqa: N802
        from .procedure.statements import SubtractStatement

        return self._build(SubtractStatement, ctx)

    def visitMultiplyStatement(self, ctx):  # noqa: N802
        from .procedure.statements import MultiplyStatement

        return self._build(MultiplyStatement, ctx)

    def visitDivideStatement(self, ctx):  # noqa: N802
        from .procedure.statements import DivideStatement

        return self._build(DivideStatement, ctx)

    def visitComputeStatement(self, ctx):  # noqa: N802
        from .procedure.statements import ComputeStatement

        return self._build(ComputeStatement, ctx)

    def visitIfStatement(self, ctx):  # noqa: N802
        from .procedure.statements import IfStatement

        return self._build(IfStatement, ctx)

    def visitPerformStatement(self, ctx):  # noqa: N802
        from .procedure.statements import PerformStatement

        return self._build(PerformStatement, ctx)

    def visitGoToStatement(self, ctx):  # noqa: N802
        from .procedure.statements import GoToStatement

        return self._build(GoToStatement, ctx)

    def visitDisplayStatement(self, ctx):  # noqa: N802
        from .procedure.statements import DisplayStatement

        return self._build(DisplayStatement, ctx)

    def visitStopStatement(self, ctx):  # noqa: N802
        from .procedure.statements import StopStatement

        return self._build(StopStatement, ctx)

    def visitContinueStatement(self, ctx):  # noqa: N802
        from .procedure.statements import ContinueStatement

        return self._build(ContinueStatement, ctx)

    def visitExitStatement(self, ctx):  # noqa: N802
        from .procedure.statements import ExitStatement

        return self._build(ExitStatement, ctx)

    def visitGobackStatement(self, ctx):  # noqa: N802
        from .procedure.statements import GobackStatement

        return self._build(GobackStatement, ctx)

    def visitMoveStatement(self, ctx):  # noqa: N802
        from .procedure.statements import MoveStatement

        return self._build(MoveStatement, ctx)
