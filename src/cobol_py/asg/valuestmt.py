"""Value statement metamodel.

Ports ``metamodel/valuestmt`` — the full expression tree decomposition for
arithmetic expressions, conditions, relation conditions, and IN references.

Grammar-driven tree structure (matches Cobol.g4)::

    ArithmeticExpression
    ├── MultDivs (first term)
    │   ├── Powers (unary +/- basis power*)
    │   └── MultDiv (*|/ powers)  ← repeated
    └── PlusMinus (+|- MultDivs)  ← repeated

    Condition
    ├── CombinableCondition (NOT? SimpleCondition)
    └── AndOrCondition (AND|OR CombinableCondition)  ← repeated

    SimpleCondition dispatches to one of:
    ├── RelationConditionValueStmt  (comparison)
    ├── ClassCondition             (NUMERIC/ALPHABETIC/...)
    ├── ConditionNameReference     (88-level)
    └── ConditionValueStmt         (parenthesized sub-condition)
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from antlr4.ParserRuleContext import ParserRuleContext

from .base import CobolDivisionElement
from .literal import IntegerLiteral, Literal


def _has(ctx, token_name: str) -> bool:
    """Return ``True`` if the named ANTLR typed token is present on ``ctx``."""
    accessor = getattr(ctx, token_name, None)
    return callable(accessor) and accessor() is not None


# -- enums -------------------------------------------------------------------

class PlusMinusType(Enum):
    PLUS = "PLUS"
    MINUS = "MINUS"


class MultDivType(Enum):
    MULT = "MULT"
    DIV = "DIV"


class PowersType(Enum):
    PLUS = "PLUS"
    MINUS = "MINUS"


class AndOrConditionType(Enum):
    AND = "AND"
    OR = "OR"


class SimpleConditionType(Enum):
    CLASS_CONDITION = "CLASS_CONDITION"
    CONDITION = "CONDITION"
    CONDITION_NAME_REFERENCE = "CONDITION_NAME_REFERENCE"
    RELATION_CONDITION = "RELATION_CONDITION"


class ClassConditionType(Enum):
    ALPHABETIC = "ALPHABETIC"
    ALPHABETIC_LOWER = "ALPHABETIC_LOWER"
    ALPHABETIC_UPPER = "ALPHABETIC_UPPER"
    CLASS_NAME = "CLASS_NAME"
    DBCS = "DBCS"
    KANJI = "KANJI"
    NUMERIC = "NUMERIC"


class RelationalOperatorType(Enum):
    EQUAL = "EQUAL"
    GREATER = "GREATER"
    GREATER_OR_EQUAL = "GREATER_OR_EQUAL"
    LESS = "LESS"
    LESS_OR_EQUAL = "LESS_OR_EQUAL"
    NOT_EQUAL = "NOT_EQUAL"


class SignConditionType(Enum):
    NEGATIVE = "NEGATIVE"
    POSITIVE = "POSITIVE"
    ZERO = "ZERO"


class CombinedConditionType(Enum):
    AND = "AND"
    OR = "OR"


# -- base value statement classes --------------------------------------------

class ValueStmt(CobolDivisionElement):
    """Base for all value statements (literal, call, arithmetic, condition)."""

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


class BooleanLiteralValueStmt(ValueStmt):
    """A ``TRUE`` / ``FALSE`` literal used as a standalone value statement.

    Ports ``valuestmt/BooleanLiteralValueStmt``. Used in EVALUATE WHEN
    branches (``WHEN TRUE``) and similar contexts.
    """

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.boolean_literal = None


class Argument(CobolDivisionElement):
    """Marker element wrapping an ``argument`` grammar context.

    Ports ``valuestmt/Argument``. No extra fields beyond the ctx;
    used as a structural node in the ASG tree.
    """


# ============================================================================
# arithmetic expression tree
# ============================================================================

class Basis(ValueStmt):
    """Leaf: ``identifier | literal | (arithmeticExpression)``. Ports ``arithmetic/Basis``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.basis_value_stmt: Optional[ValueStmt] = None

    def _populate(self) -> None:
        ctx = self.ctx
        # identifier
        ident = ctx.identifier()
        lit = ctx.literal()
        if ident is not None:
            call = self.create_call(ident)
            if call is not None:
                self.basis_value_stmt = CallValueStmt(call, self.program_unit, ident)
        elif lit is not None:
            self.basis_value_stmt = self.create_value_stmt(lit)
        # parenthesized sub-expression
        ae = ctx.arithmeticExpression()
        if ae is not None:
            sub = ArithmeticValueStmt(self.program_unit, ae)
            sub._populate()
            self.basis_value_stmt = sub


class Power(ValueStmt):
    """``** basis``. Ports ``arithmetic/Power``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.basis: Optional[Basis] = None

    def _populate(self) -> None:
        basis_ctx = self.ctx.basis()
        if basis_ctx is not None:
            self.basis = Basis(self.program_unit, basis_ctx)
            self.basis._populate()


class Powers(ValueStmt):
    """``[+|-] basis power*``. Ports ``arithmetic/Powers``.

    The optional unary sign is at this level.
    """

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.powers_type: Optional[PowersType] = None
        self.basis: Optional[Basis] = None
        self.powers: List[Power] = []

    def _populate(self) -> None:
        ctx = self.ctx
        # unary sign
        if _has(ctx, "MINUSCHAR"):
            self.powers_type = PowersType.MINUS
        elif _has(ctx, "PLUSCHAR"):
            self.powers_type = PowersType.PLUS
        # basis
        basis_ctx = ctx.basis()
        if basis_ctx is not None:
            self.basis = Basis(self.program_unit, basis_ctx)
            self.basis._populate()
        # power chain
        for power_ctx in ctx.power():
            p = Power(self.program_unit, power_ctx)
            p._populate()
            self.powers.append(p)


class MultDiv(ValueStmt):
    """``*|/ powers``. Ports ``arithmetic/MultDiv``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.mult_div_type: Optional[MultDivType] = None
        self.powers: Optional[Powers] = None

    def _populate(self) -> None:
        ctx = self.ctx
        if _has(ctx, "ASTERISKCHAR"):
            self.mult_div_type = MultDivType.MULT
        elif _has(ctx, "SLASHCHAR"):
            self.mult_div_type = MultDivType.DIV
        powers_ctx = ctx.powers()
        if powers_ctx is not None:
            self.powers = Powers(self.program_unit, powers_ctx)
            self.powers._populate()


class MultDivs(ValueStmt):
    """``powers multDiv*``. Ports ``arithmetic/MultDivs``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.powers: Optional[Powers] = None
        self.mult_divs: List[MultDiv] = []

    def _populate(self) -> None:
        ctx = self.ctx
        powers_ctx = ctx.powers()
        if powers_ctx is not None:
            self.powers = Powers(self.program_unit, powers_ctx)
            self.powers._populate()
        for md_ctx in ctx.multDiv():
            md = MultDiv(self.program_unit, md_ctx)
            md._populate()
            self.mult_divs.append(md)


class PlusMinus(ValueStmt):
    """``+|- MultDivs`` (mandatory sign). Ports ``arithmetic/PlusMinus``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.plus_minus_type: Optional[PlusMinusType] = None
        self.mult_divs: Optional[MultDivs] = None

    def _populate(self) -> None:
        ctx = self.ctx
        if _has(ctx, "MINUSCHAR"):
            self.plus_minus_type = PlusMinusType.MINUS
        elif _has(ctx, "PLUSCHAR"):
            self.plus_minus_type = PlusMinusType.PLUS
        mds = ctx.multDivs()
        if mds is not None:
            self.mult_divs = MultDivs(self.program_unit, mds)
            self.mult_divs._populate()


class ArithmeticValueStmt(ValueStmt):
    """Top-level: ``multDivs plusMinus*``. Ports ``ArithmeticValueStmt``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.mult_divs: Optional[MultDivs] = None
        self.plus_minuses: List[PlusMinus] = []

    def _populate(self) -> None:
        ctx = self.ctx
        mds = ctx.multDivs()
        if mds is not None:
            self.mult_divs = MultDivs(self.program_unit, mds)
            self.mult_divs._populate()
        for pm_ctx in ctx.plusMinus():
            pm = PlusMinus(self.program_unit, pm_ctx)
            pm._populate()
            self.plus_minuses.append(pm)


# ============================================================================
# condition tree
# ============================================================================

class RelationalOperator(ValueStmt):
    """A relational operator. Ports ``relation/RelationalOperator``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.relational_operator_type: Optional[RelationalOperatorType] = None

    def _populate(self) -> None:
        ctx = self.ctx
        # Check NOT combos first (NOT =, NOT >, NOT <) before plain operators
        if _has(ctx, "NOT"):
            if _has(ctx, "EQUALCHAR") or _has(ctx, "EQUAL"):
                self.relational_operator_type = RelationalOperatorType.NOT_EQUAL
            elif _has(ctx, "GREATER") or _has(ctx, "MORETHANCHAR"):
                self.relational_operator_type = RelationalOperatorType.GREATER_OR_EQUAL
            elif _has(ctx, "LESSTHANCHAR") or _has(ctx, "LESS"):
                self.relational_operator_type = RelationalOperatorType.GREATER_OR_EQUAL
            return
        elif _has(ctx, "MORETHANOREQUAL"):
            self.relational_operator_type = RelationalOperatorType.GREATER_OR_EQUAL
        elif _has(ctx, "LESSTHANOREQUAL"):
            self.relational_operator_type = RelationalOperatorType.LESS_OR_EQUAL
        elif _has(ctx, "MORETHANCHAR") or _has(ctx, "GREATER"):
            self.relational_operator_type = RelationalOperatorType.GREATER
        elif _has(ctx, "LESSTHANCHAR") or _has(ctx, "LESS"):
            self.relational_operator_type = RelationalOperatorType.LESS
        elif _has(ctx, "NOTEQUALCHAR"):
            self.relational_operator_type = RelationalOperatorType.NOT_EQUAL
        elif _has(ctx, "EQUALCHAR"):
            self.relational_operator_type = RelationalOperatorType.EQUAL


class ComparisonStmt(ValueStmt):
    """Base for all comparison types. Ports ``relation/ComparisonStmt``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.operator: Optional[RelationalOperator] = None


class ArithmeticComparison(ComparisonStmt):
    """``<left> <relop> <right>``. Ports ``relation/ArithmeticComparison``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.arithmetic_expression_left: Optional[ArithmeticValueStmt] = None
        self.arithmetic_expression_right: Optional[ArithmeticValueStmt] = None

    def _populate(self) -> None:
        ctx = self.ctx
        op = ctx.relationalOperator()
        if op is not None:
            self.operator = RelationalOperator(self.program_unit, op)
            self.operator._populate()
        aes = ctx.arithmeticExpression()
        if len(aes) >= 1:
            self.arithmetic_expression_left = ArithmeticValueStmt(self.program_unit, aes[0])
            self.arithmetic_expression_left._populate()
        if len(aes) >= 2:
            self.arithmetic_expression_right = ArithmeticValueStmt(self.program_unit, aes[1])
            self.arithmetic_expression_right._populate()


class CombinedCondition(ValueStmt):
    """``AND|OR <expr>`` chain. Ports ``relation/CombinedCondition``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.combined_condition_type: Optional[CombinedConditionType] = None
        self.arithmetic_expressions: List[ArithmeticValueStmt] = []

    def _populate(self) -> None:
        ctx = self.ctx
        if _has(ctx, "AND"):
            self.combined_condition_type = CombinedConditionType.AND
        elif _has(ctx, "OR"):
            self.combined_condition_type = CombinedConditionType.OR
        for ae in ctx.arithmeticExpression():
            a = ArithmeticValueStmt(self.program_unit, ae)
            a._populate()
            self.arithmetic_expressions.append(a)


class CombinedComparison(ComparisonStmt):
    """``<expr> <relop> <combined-condition>``. Ports ``relation/CombinedComparison``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.arithmetic_expression: Optional[ArithmeticValueStmt] = None
        self.combined_condition: Optional[CombinedCondition] = None

    def _populate(self) -> None:
        ctx = self.ctx
        op = ctx.relationalOperator()
        if op is not None:
            self.operator = RelationalOperator(self.program_unit, op)
            self.operator._populate()
        aes = ctx.arithmeticExpression()
        if aes:
            self.arithmetic_expression = ArithmeticValueStmt(self.program_unit, aes[0])
            self.arithmetic_expression._populate()
        cc = ctx.relationCombinedCondition()
        if cc is not None:
            self.combined_condition = CombinedCondition(self.program_unit, cc)
            self.combined_condition._populate()


class SignCondition(ValueStmt):
    """``POSITIVE|NEGATIVE|ZERO`` condition. Ports ``relation/SignCondition``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.sign_condition_type: Optional[SignConditionType] = None
        self.not_: bool = False
        self.arithmetic_expression: Optional[ArithmeticValueStmt] = None

    def _populate(self) -> None:
        ctx = self.ctx
        self.not_ = _has(ctx, "NOT")
        if _has(ctx, "POSITIVE"):
            self.sign_condition_type = SignConditionType.POSITIVE
        elif _has(ctx, "NEGATIVE"):
            self.sign_condition_type = SignConditionType.NEGATIVE
        elif _has(ctx, "ZERO") or _has(ctx, "ZEROS") or _has(ctx, "ZEROES"):
            self.sign_condition_type = SignConditionType.ZERO
        ae = ctx.arithmeticExpression()
        if ae is not None:
            self.arithmetic_expression = ArithmeticValueStmt(self.program_unit, ae)
            self.arithmetic_expression._populate()


class Abbreviation(ComparisonStmt):
    """Abbreviated combined relation. Ports ``relation/Abbreviation``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.arithmetic_expression: Optional[ArithmeticValueStmt] = None
        self.abbreviation: Optional["Abbreviation"] = None

    def _populate(self) -> None:
        ctx = self.ctx
        op = ctx.relationalOperator()
        if op is not None:
            self.operator = RelationalOperator(self.program_unit, op)
            self.operator._populate()
        ae = ctx.arithmeticExpression()
        if ae is not None:
            self.arithmetic_expression = ArithmeticValueStmt(self.program_unit, ae)
            self.arithmetic_expression._populate()
        abbr = ctx.abbreviation()
        if abbr is not None:
            self.abbreviation = Abbreviation(self.program_unit, abbr)
            self.abbreviation._populate()


class RelationConditionValueStmt(ValueStmt):
    """A relation condition. Ports ``RelationConditionValueStmt``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.comparison_stmt: Optional[ComparisonStmt] = None

    def _populate(self) -> None:
        ctx = self.ctx

        sc = ctx.relationSignCondition()
        if sc is not None:
            cs = SignCondition(self.program_unit, sc)
            cs._populate()
            self.comparison_stmt = cs
            return

        ac = ctx.relationArithmeticComparison()
        if ac is not None:
            cs = ArithmeticComparison(self.program_unit, ac)
            cs._populate()
            self.comparison_stmt = cs
            return

        cc = ctx.relationCombinedComparison()
        if cc is not None:
            cs = CombinedComparison(self.program_unit, cc)
            cs._populate()
            self.comparison_stmt = cs
            return

        ab = ctx.abbreviation()
        if ab is not None:
            cs = Abbreviation(self.program_unit, ab)
            cs._populate()
            self.comparison_stmt = cs
            return


class ClassCondition(ValueStmt):
    """``identifier IS [NOT] (NUMERIC|ALPHABETIC|...)``. Ports ``condition/ClassCondition``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.class_condition_type: Optional[ClassConditionType] = None
        self.not_: bool = False
        self.identifier_call = None
        self.class_call = None

    def _populate(self) -> None:
        ctx = self.ctx
        self.not_ = _has(ctx, "NOT")
        if _has(ctx, "ALPHABETIC_UPPER"):
            self.class_condition_type = ClassConditionType.ALPHABETIC_UPPER
        elif _has(ctx, "ALPHABETIC_LOWER"):
            self.class_condition_type = ClassConditionType.ALPHABETIC_LOWER
        elif _has(ctx, "ALPHABETIC"):
            self.class_condition_type = ClassConditionType.ALPHABETIC
        elif _has(ctx, "DBCS"):
            self.class_condition_type = ClassConditionType.DBCS
        elif _has(ctx, "KANJI"):
            self.class_condition_type = ClassConditionType.KANJI
        elif _has(ctx, "NUMERIC"):
            self.class_condition_type = ClassConditionType.NUMERIC
        ident = ctx.identifier()
        if ident is not None:
            self.identifier_call = self.create_call(ident)
        cn = ctx.className()
        if cn is not None:
            self.class_call = self.create_call(cn)


class ConditionNameSubscriptReference(ValueStmt):
    """Subscript references for a condition-name. Ports ``condition/ConditionNameSubscriptReference``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.subscripts: List = []

    def _populate(self) -> None:
        for sub_ctx in self.ctx.subscript():
            s = self.create_value_stmt(sub_ctx)
            if s is not None:
                self.subscripts.append(s)


# -- IN sub-models -----------------------------------------------------------

class InData(CobolDivisionElement):
    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_call = None


class InFile(CobolDivisionElement):
    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.file_call = None


class InMnemonic(CobolDivisionElement):
    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.mnemonic_call = None


class InSection(CobolDivisionElement):
    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.section_call = None


class InTable(CobolDivisionElement):
    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.table_call = None


class InLibrary(CobolDivisionElement):
    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.library_call = None


class ConditionNameReference(ValueStmt):
    """Reference to an 88-level condition-name. Ports ``condition/ConditionNameReference``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.condition_call = None
        self.condition_name_subscript_references: List[ConditionNameSubscriptReference] = []
        self.in_datas: List[InData] = []
        self.in_file: Optional[InFile] = None
        self.in_mnemonics: List[InMnemonic] = []

    def _populate(self) -> None:
        ctx = self.ctx
        cn = ctx.conditionName()
        if cn is not None:
            self.condition_call = self.create_call(cn)
        for sr in ctx.conditionNameSubscriptReference():
            ref = ConditionNameSubscriptReference(self.program_unit, sr)
            ref._populate()
            self.condition_name_subscript_references.append(ref)
        for id_ctx in ctx.inData():
            d = InData(self.program_unit, id_ctx)
            dn = id_ctx.dataName()
            if dn is not None:
                d.data_call = self.create_call(dn)
            self.in_datas.append(d)
        if_ctx = ctx.inFile()
        if if_ctx is not None:
            f = InFile(self.program_unit, if_ctx)
            fn = if_ctx.fileName()
            if fn is not None:
                f.file_call = self.create_call(fn)
            self.in_file = f
        for im_ctx in ctx.inMnemonic():
            m = InMnemonic(self.program_unit, im_ctx)
            mn = im_ctx.mnemonicName()
            if mn is not None:
                m.mnemonic_call = self.create_call(mn)
            self.in_mnemonics.append(m)


class SimpleCondition(ValueStmt):
    """A simple condition. Ports ``condition/SimpleCondition``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.simple_condition_type: Optional[SimpleConditionType] = None
        self.relation_condition: Optional[RelationConditionValueStmt] = None
        self.class_condition: Optional[ClassCondition] = None
        self.condition_name_reference: Optional[ConditionNameReference] = None
        self.condition: Optional[ConditionValueStmt] = None

    def _populate(self) -> None:
        ctx = self.ctx
        rc = ctx.relationCondition()
        if rc is not None:
            self.simple_condition_type = SimpleConditionType.RELATION_CONDITION
            self.relation_condition = RelationConditionValueStmt(self.program_unit, rc)
            self.relation_condition._populate()
            return
        cc = ctx.classCondition()
        if cc is not None:
            self.simple_condition_type = SimpleConditionType.CLASS_CONDITION
            self.class_condition = ClassCondition(self.program_unit, cc)
            self.class_condition._populate()
            return
        cnr = ctx.conditionNameReference()
        if cnr is not None:
            self.simple_condition_type = SimpleConditionType.CONDITION_NAME_REFERENCE
            self.condition_name_reference = ConditionNameReference(self.program_unit, cnr)
            self.condition_name_reference._populate()
            return
        cond = ctx.condition()
        if cond is not None:
            self.simple_condition_type = SimpleConditionType.CONDITION
            self.condition = ConditionValueStmt(self.program_unit, cond)
            self.condition._populate()
            return


class CombinableCondition(ValueStmt):
    """``[NOT] simpleCondition``. Ports ``condition/CombinableCondition``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.not_: bool = False
        self.simple_condition: Optional[SimpleCondition] = None

    def _populate(self) -> None:
        ctx = self.ctx
        self.not_ = _has(ctx, "NOT")
        sc = ctx.simpleCondition()
        if sc is not None:
            self.simple_condition = SimpleCondition(self.program_unit, sc)
            self.simple_condition._populate()


class AndOrCondition(ValueStmt):
    """``AND|OR combinableCondition`` (mandatory connective). Ports ``condition/AndOrCondition``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.and_or_condition_type: Optional[AndOrConditionType] = None
        self.combinable_condition: Optional[CombinableCondition] = None

    def _populate(self) -> None:
        ctx = self.ctx
        if _has(ctx, "AND"):
            self.and_or_condition_type = AndOrConditionType.AND
        elif _has(ctx, "OR"):
            self.and_or_condition_type = AndOrConditionType.OR
        cc = ctx.combinableCondition()
        if cc is not None:
            self.combinable_condition = CombinableCondition(self.program_unit, cc)
            self.combinable_condition._populate()


class ConditionValueStmt(ValueStmt):
    """Top-level: ``combinableCondition andOrCondition*``. Ports ``ConditionValueStmt``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, ctx)
        self.combinable_condition: Optional[CombinableCondition] = None
        self.and_or_conditions: List[AndOrCondition] = []

    def _populate(self) -> None:
        ctx = self.ctx
        cc = ctx.combinableCondition()
        if cc is not None:
            self.combinable_condition = CombinableCondition(self.program_unit, cc)
            self.combinable_condition._populate()
        for aoc in ctx.andOrCondition():
            ao = AndOrCondition(self.program_unit, aoc)
            ao._populate()
            self.and_or_conditions.append(ao)
