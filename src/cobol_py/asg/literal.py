"""Literal metamodel.

Ports ``metamodel/{Literal,IntegerLiteral,NumericLiteral,BooleanLiteral,
FigurativeConstant}`` (interface + impl collapsed).
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Optional

from antlr4.ParserRuleContext import ParserRuleContext

from .base import CobolDivisionElement


class IntegerLiteral(CobolDivisionElement):
    """An integer literal (value as :class:`decimal.Decimal`)."""

    def __init__(self, value: Optional[Decimal], program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.value = value


class NumericLiteral(CobolDivisionElement):
    class Type(Enum):
        INTEGER = "INTEGER"
        FLOAT = "FLOAT"

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.value: Optional[Decimal] = None
        self.numeric_literal_type: Optional[NumericLiteral.Type] = None


class BooleanLiteral(CobolDivisionElement):
    def __init__(self, value: Optional[bool], program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.value = value


class FigurativeConstant(CobolDivisionElement):
    class Type(Enum):
        ALL = "ALL"
        HIGH_VALUE = "HIGH_VALUE"
        HIGH_VALUES = "HIGH_VALUES"
        LOW_VALUE = "LOW_VALUE"
        LOW_VALUES = "LOW_VALUES"
        NULL = "NULL"
        NULLS = "NULLS"
        QUOTE = "QUOTE"
        QUOTES = "QUOTES"
        SPACE = "SPACE"
        SPACES = "SPACES"
        ZERO = "ZERO"
        ZEROS = "ZEROS"
        ZEROES = "ZEROES"

    def __init__(self, figurative_type, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.figurative_constant_type: Optional[FigurativeConstant.Type] = figurative_type
        self.literal: Optional[Literal] = None


class Literal(CobolDivisionElement):
    """A COBOL literal: non-numeric, numeric, boolean, or figurative constant."""

    class Type(Enum):
        BOOLEAN = "BOOLEAN"
        CICS_DFH_RESP = "CICS_DFH_RESP"
        CICS_DFH_VALUE = "CICS_DFH_VALUE"
        FIGURATIVE_CONSTANT = "FIGURATIVE_CONSTANT"
        NON_NUMERIC = "NON_NUMERIC"
        NUMERIC = "NUMERIC"

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.literal_type: Optional[Literal.Type] = None
        self.non_numeric_literal: Optional[str] = None
        self.numeric_literal: Optional[NumericLiteral] = None
        self.boolean_literal: Optional[BooleanLiteral] = None
        self.figurative_constant: Optional[FigurativeConstant] = None

    @property
    def value(self):
        if self.literal_type == Literal.Type.NON_NUMERIC:
            return self.non_numeric_literal
        if self.literal_type == Literal.Type.NUMERIC:
            return self.numeric_literal.value if self.numeric_literal else None
        if self.literal_type == Literal.Type.BOOLEAN:
            return self.boolean_literal.value if self.boolean_literal else None
        if self.literal_type == Literal.Type.FIGURATIVE_CONSTANT:
            return self.figurative_constant
        return None
