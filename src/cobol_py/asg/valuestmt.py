"""Value statement metamodel.

Ports ``metamodel/valuestmt`` (interface + impl collapsed). A :class:`ValueStmt`
wraps a literal, call, arithmetic expression, or condition as it appears in a
statement operand. Full arithmetic/condition decomposition (MultDivs, PlusMinus,
CombinableCondition, AndOrCondition) is deferred to a later phase; for now
:class:`ArithmeticValueStmt` and :class:`ConditionValueStmt` retain their ctx.
"""

from __future__ import annotations

from typing import List, Optional

from antlr4.ParserRuleContext import ParserRuleContext

from .base import CobolDivisionElement
from .literal import Literal, IntegerLiteral


class ValueStmt(CobolDivisionElement):
    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.sub_value_stmts: List[ValueStmt] = []


class LiteralValueStmt(ValueStmt):
    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.literal: Optional[Literal] = None


class IntegerLiteralValueStmt(ValueStmt):
    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.integer_literal: Optional[IntegerLiteral] = None


class CallValueStmt(ValueStmt):
    def __init__(self, call, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.call = call


class ConditionValueStmt(ValueStmt):
    """An IF/condition operand. Decomposition deferred; ``ctx`` is retained."""


class ArithmeticValueStmt(ValueStmt):
    """An arithmetic expression operand. Decomposition deferred; ``ctx`` retained."""
