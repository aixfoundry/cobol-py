"""cobol_py.asg - the Abstract Semantic Graph layer (port of proleap's ASG).

Builds a typed, registry-backed object model of a COBOL program on top of the
AST produced by :class:`cobol_py.runner.CobolParserRunner`. Entry point::

    from cobol_py import CobolParserRunner, CobolSourceFormatEnum
    program = CobolParserRunner().analyze_file("x.cbl", CobolSourceFormatEnum.FIXED)
    for stmt in program.compilation_unit.program_unit.procedure_division.paragraphs[0].statements:
        print(stmt.statement_type)
"""

from __future__ import annotations

from .antlr_utils import find_ancestors, find_children, find_parent
from .base import (
    ASGElement,
    CobolDivisionElement,
    CompilationUnitElement,
    Declaration,
    NamedElement,
    ProgramUnitElement,
)
from .call import (
    Call,
    CallDelegate,
    CallTypeEnum,
    DataDescriptionEntryCall,
    ProcedureCall,
    SectionCall,
    UndefinedCall,
)
from .identification import IdentificationDivision, ProgramIdParagraph
from .literal import (
    BooleanLiteral,
    FigurativeConstant,
    IntegerLiteral,
    Literal,
    NumericLiteral,
)
from .procedure.division import (
    Paragraph,
    ParagraphName,
    ProcedureDivision,
    Scope,
    Section,
    Statement,
    StatementTypeEnum,
)
from .procedure.statements import (
    AcceptStatement,
    AddStatement,
    ComputeStatement,
    ContinueStatement,
    DisplayStatement,
    DivideStatement,
    ExitStatement,
    GobackStatement,
    GoToStatement,
    IfStatement,
    MoveStatement,
    MultiplyStatement,
    PerformStatement,
    StopStatement,
    SubtractStatement,
)
from .program import (
    CompilationUnit,
    DataDivision,
    EnvironmentDivision,
    Program,
    ProgramUnit,
)
from .registry import ASGElementRegistry
from .resolver import determine_name
from .valuestmt import (
    ArithmeticValueStmt,
    CallValueStmt,
    ConditionValueStmt,
    IntegerLiteralValueStmt,
    LiteralValueStmt,
    ValueStmt,
)
from .visitor import (
    AbstractCobolParserVisitor,
    CobolCompilationUnitVisitor,
    CobolProcedureDivisionVisitor,
    CobolProcedureStatementVisitor,
    CobolProgramUnitVisitor,
)

__all__ = [
    "ASGElement",
    "ASGElementRegistry",
    "AbstractCobolParserVisitor",
    "AcceptStatement",
    "AddStatement",
    "ArithmeticValueStmt",
    "BooleanLiteral",
    "Call",
    "CallDelegate",
    "CallTypeEnum",
    "CallValueStmt",
    "CobolCompilationUnitVisitor",
    "CobolDivisionElement",
    "CobolProcedureDivisionVisitor",
    "CobolProcedureStatementVisitor",
    "CobolProgramUnitVisitor",
    "CompilationUnit",
    "CompilationUnitElement",
    "ComputeStatement",
    "ConditionValueStmt",
    "ContinueStatement",
    "DataDescriptionEntryCall",
    "DataDivision",
    "Declaration",
    "DisplayStatement",
    "DivideStatement",
    "EnvironmentDivision",
    "ExitStatement",
    "FigurativeConstant",
    "GobackStatement",
    "GoToStatement",
    "IdentificationDivision",
    "IfStatement",
    "IntegerLiteral",
    "IntegerLiteralValueStmt",
    "Literal",
    "LiteralValueStmt",
    "MoveStatement",
    "MultiplyStatement",
    "NamedElement",
    "NumericLiteral",
    "Paragraph",
    "ParagraphName",
    "PerformStatement",
    "ProcedureCall",
    "ProcedureDivision",
    "Program",
    "ProgramIdParagraph",
    "ProgramUnit",
    "ProgramUnitElement",
    "Scope",
    "Section",
    "SectionCall",
    "Statement",
    "StatementTypeEnum",
    "StopStatement",
    "SubtractStatement",
    "UndefinedCall",
    "ValueStmt",
    "determine_name",
    "find_ancestors",
    "find_children",
    "find_parent",
]
