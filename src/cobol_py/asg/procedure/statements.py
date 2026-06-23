"""The 15 core procedure statements (Phase C1).

Each statement subclasses :class:`Statement` via :class:`_StatementBase`, which
provides ``build`` (construct + populate + register on the scope) and a
``_populate`` hook. The statement-dispatch visitor lazy-imports these and calls
``build``.

Scope note: statements nested inside IF/PERFORM-inline still attach to the
enclosing paragraph/section scope (so they appear in ``scope.statements``);
dedicated Then/Else and inline-body containers, plus full arithmetic/condition
decomposition, are deferred to a later phase. The showcase details — MOVE
receiving calls, PERFORM resolved procedure calls, DISPLAY operands, and the IF
condition — are captured faithfully here.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from antlr4.ParserRuleContext import ParserRuleContext

from ..base import CobolDivisionElement
from .division import Scope, Statement, StatementTypeEnum


class _StatementBase(Statement):
    """Provides ``build`` and a no-op ``_populate`` for the simple verbs."""

    statement_type: Optional[StatementTypeEnum] = None

    @classmethod
    def build(cls, scope, ctx: ParserRuleContext):
        stmt = cls(scope.program_unit, scope, ctx)
        stmt._populate()
        scope.register_statement(stmt)
        return stmt

    def _populate(self) -> None:
        pass

    def _build_phrase_scope(self, phrase_cls, ctx: ParserRuleContext):
        """Build (and register) a phrase :class:`Scope` around ``ctx``.

        Phrase scopes (AT END, THEN/ELSE, PERFORM inline body, ...) own their
        nested statements: because they are registered before the dispatch
        visitor recurses into them, ``find_scope`` returns the phrase for the
        nested verbs, so they register on the phrase instead of leaking to the
        enclosing paragraph. Mirrors proleap, where these phrases implement
        ``Scope`` and ``ANTLRUtils.findParent(Scope.class, ...)`` finds them.
        """
        result = self._get_element(ctx)
        if result is None:
            result = phrase_cls(self.program_unit, ctx)
            sentence_token = getattr(ctx, "SENTENCE", None)
            if callable(sentence_token) and sentence_token() is not None:
                result.next_sentence = True
            self._register(result)
        return result

    def _phrase(self, phrase_cls, ctx: Optional[ParserRuleContext]):
        """Build+register a phrase :class:`Scope` iff ``ctx`` is present.

        COBOL phrase clauses (AT END, INVALID KEY, ON SIZE ERROR, ...) are all
        optional; their ANTLR accessors return ``None`` when absent. This wraps
        :meth:`_build_phrase_scope` so callers can write one line per phrase
        without a guard.
        """
        if ctx is None:
            return None
        return self._build_phrase_scope(phrase_cls, ctx)


# --- MOVE ------------------------------------------------------------------

class MoveToSendingArea(CobolDivisionElement):
    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.sending_area_value_stmt = None


class MoveToStatement(CobolDivisionElement):
    """The ``TO`` form of MOVE: one sending area + N receiving-area calls."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.sending_area: Optional[MoveToSendingArea] = None
        self.receiving_area_calls: List = []

    @classmethod
    def build(cls, move_statement, ctx: ParserRuleContext) -> "MoveToStatement":
        result = move_statement._get_element(ctx)
        if result is None:
            result = cls(move_statement.program_unit, ctx)
            result._populate()
            move_statement._register(result)
        return result

    def _populate(self) -> None:
        ctx = self.ctx
        sending = ctx.moveToSendingArea()
        if sending is not None:
            area = self._get_element(sending)
            if area is None:
                area = MoveToSendingArea(self.program_unit, sending)
                area.sending_area_value_stmt = self.create_value_stmt(
                    sending.identifier(), sending.literal()
                )
                self._register(area)
            self.sending_area = area
        for identifier_ctx in ctx.identifier():
            self.receiving_area_calls.append(self.create_call(identifier_ctx))


class MoveStatement(_StatementBase):
    statement_type = StatementTypeEnum.MOVE

    class MoveType(Enum):
        MOVE_TO = "MOVE_TO"
        MOVE_CORRESPONDING = "MOVE_CORRESPONDING"

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.move_type: Optional[MoveStatement.MoveType] = None
        self.move_to: Optional[MoveToStatement] = None
        self.move_corresponding = None

    def _populate(self) -> None:
        ctx = self.ctx
        if ctx.moveToStatement() is not None:
            self.move_to = MoveToStatement.build(self, ctx.moveToStatement())
            self.move_type = MoveStatement.MoveType.MOVE_TO
        elif ctx.moveCorrespondingToStatement() is not None:
            self.move_type = MoveStatement.MoveType.MOVE_CORRESPONDING
            # full MOVE CORRESPONDING decomposition deferred


# --- PERFORM ---------------------------------------------------------------

class PerformProcedureStatement(CobolDivisionElement):
    """A ``PERFORM <proc> [THROUGH <proc>]``: one or more resolved calls."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.calls: List = []

    @classmethod
    def build(cls, perform_statement, ctx: ParserRuleContext) -> "PerformProcedureStatement":
        result = perform_statement._get_element(ctx)
        if result is None:
            result = cls(perform_statement.program_unit, ctx)
            result._populate()
            perform_statement._register(result)
        return result

    def _populate(self) -> None:
        procedure_names = self.ctx.procedureName()
        if not procedure_names:
            return
        self.calls.append(self.create_call(procedure_names[0]))
        if len(procedure_names) > 1:
            # THROUGH range: the through-range expansion (addCallsThrough) is
            # deferred; for now both endpoints are captured as calls.
            self.calls.append(self.create_call(procedure_names[1]))


class PerformStatement(_StatementBase):
    statement_type = StatementTypeEnum.PERFORM

    class PerformType(Enum):
        INLINE = "INLINE"
        PROCEDURE = "PROCEDURE"

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.perform_type: Optional[PerformStatement.PerformType] = None
        self.perform_procedure_statement: Optional[PerformProcedureStatement] = None
        self.perform_inline_statement = None

    def _populate(self) -> None:
        ctx = self.ctx
        if ctx.performProcedureStatement() is not None:
            self.perform_procedure_statement = PerformProcedureStatement.build(
                self, ctx.performProcedureStatement()
            )
            self.perform_type = PerformStatement.PerformType.PROCEDURE
        elif ctx.performInlineStatement() is not None:
            self.perform_type = PerformStatement.PerformType.INLINE
            inline_ctx = ctx.performInlineStatement()
            container = self._get_element(inline_ctx)
            if container is None:
                container = PerformInlineStatement(self.program_unit, inline_ctx)
                self._register(container)
            self.perform_inline_statement = container


# --- DISPLAY ---------------------------------------------------------------

class DisplayOperand(CobolDivisionElement):
    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.operand_value_stmt = None


class DisplayStatement(_StatementBase):
    statement_type = StatementTypeEnum.DISPLAY

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.operands: List[DisplayOperand] = []
        self.on_exception_clause: Optional[OnExceptionClause] = None
        self.not_on_exception_clause: Optional[NotOnExceptionClause] = None

    def _populate(self) -> None:
        ctx = self.ctx
        for operand_ctx in ctx.displayOperand():
            operand = self._get_element(operand_ctx)
            if operand is None:
                operand = DisplayOperand(self.program_unit, operand_ctx)
                operand.operand_value_stmt = self.create_value_stmt(
                    operand_ctx.identifier(), operand_ctx.literal()
                )
                self._register(operand)
            self.operands.append(operand)
        self.on_exception_clause = self._phrase(
            OnExceptionClause, ctx.onExceptionClause()
        )
        self.not_on_exception_clause = self._phrase(
            NotOnExceptionClause, ctx.notOnExceptionClause()
        )


# --- IF --------------------------------------------------------------------

class IfStatement(_StatementBase):
    statement_type = StatementTypeEnum.IF

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.condition = None  # ConditionValueStmt
        self.then: Optional[Then] = None
        self.else_: Optional[Else] = None

    def _populate(self) -> None:
        ctx = self.ctx
        condition_ctx = ctx.condition()
        if condition_ctx is not None:
            self.condition = self.create_condition_value_stmt(condition_ctx)
        then_ctx = ctx.ifThen()
        if then_ctx is not None:
            self.then = self._build_phrase_scope(Then, then_ctx)
        else_ctx = ctx.ifElse()
        if else_ctx is not None:
            self.else_ = self._build_phrase_scope(Else, else_ctx)


# --- ACCEPT / GOTO ---------------------------------------------------------

class AcceptStatement(_StatementBase):
    statement_type = StatementTypeEnum.ACCEPT

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.receiving_call = None
        self.on_exception_clause: Optional[OnExceptionClause] = None
        self.not_on_exception_clause: Optional[NotOnExceptionClause] = None

    def _populate(self) -> None:
        ctx = self.ctx
        identifier_ctx = ctx.identifier()
        if identifier_ctx is not None:
            self.receiving_call = self.create_call(identifier_ctx)
        self.on_exception_clause = self._phrase(
            OnExceptionClause, ctx.onExceptionClause()
        )
        self.not_on_exception_clause = self._phrase(
            NotOnExceptionClause, ctx.notOnExceptionClause()
        )


class GoToStatement(_StatementBase):
    statement_type = StatementTypeEnum.GO_TO

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.calls: List = []

    def _populate(self) -> None:
        # GO TO nests under goToStatementSimple / goToDependingOnStatement, each
        # carrying the target procedureName(s). Walk the ctx for ProcedureNameContext
        # nodes so both forms resolve.
        stack = [self.ctx]
        seen = set()
        while stack:
            node = stack.pop()
            if node is None or id(node) in seen:
                continue
            seen.add(id(node))
            if type(node).__name__ == "ProcedureNameContext":
                self.calls.append(self.create_call(node))
                continue
            for i in range(getattr(node, "getChildCount", lambda: 0)()):
                stack.append(node.getChild(i))


# --- STOP (with optional display literal) ----------------------------------

class StopStatement(_StatementBase):
    statement_type = StatementTypeEnum.STOP

    class StopType(Enum):
        STOP_RUN = "STOP_RUN"
        STOP_RUN_AND_DISPLAY = "STOP_RUN_AND_DISPLAY"
        STOP_RUN_GIVING = "STOP_RUN_GIVING"

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.stop_type: Optional[StopStatement.StopType] = None
        self.display_value_stmt = None

    def _populate(self) -> None:
        ctx = self.ctx
        if ctx.literal() is not None:
            self.stop_type = StopStatement.StopType.STOP_RUN_AND_DISPLAY
            self.display_value_stmt = self.create_value_stmt(ctx.literal())
        elif ctx.stopStatementGiving() is not None:
            self.stop_type = StopStatement.StopType.STOP_RUN_GIVING
        else:
            self.stop_type = StopStatement.StopType.STOP_RUN


# --- leaf statements -------------------------------------------------------

class ContinueStatement(_StatementBase):
    statement_type = StatementTypeEnum.CONTINUE


class ExitStatement(_StatementBase):
    statement_type = StatementTypeEnum.EXIT


class GobackStatement(_StatementBase):
    statement_type = StatementTypeEnum.GO_BACK


# --- arithmetic (ADD/SUBTRACT/MULTIPLY/DIVIDE/COMPUTe) --------------------
# Each verb keeps the shared ON / NOT ON SIZE ERROR phrase ownership from the
# base and adds its own operand/clause decomposition. Ports the Java
# ``ScopeImpl.add{Add,Subtract,Multiply,Divide,Compute}Statement`` builders and
# the per-verb ``*StatementImpl`` sub-builders (From/To/Giving/Store/Remainder/
# ByPhrase/...). Receiving targets that may carry ROUNDED (addTo, addGiving,
# divideInto, divideGiving, multiplyRegularOperand, multiplyGivingResult,
# subtractMinuend, subtractGiving, computeStore) are wrapped in
# :class:`_RoundedCall`; pure ``identifier | literal`` operands become ValueStmts.


class _RoundedCall:
    """A receiving target carrying an optional ROUNDED flag.

    Collapses proleap's per-verb leaf wrappers (``To`` / ``Giving`` / ``Into``
    / ``Store`` / ``MultiplyRegularOperand`` / ``SubtractMinuend`` / ...), each
    of which holds a ``Call`` plus a boolean ``rounded``.
    """

    __slots__ = ("call", "rounded")

    def __init__(self, call, rounded: bool = False) -> None:
        self.call = call
        self.rounded = rounded


class _ArithmeticStatementBase(_StatementBase):
    """Base for ADD/SUBTRACT/MULTIPLY/DIVIDE/COMPUTE.

    Owns the ``ON SIZE ERROR`` / ``NOT ON SIZE ERROR`` phrases so their nested
    statements do not leak to the enclosing paragraph; per-verb operands are
    filled by each subclass's ``_populate`` override.
    """

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.on_size_error_phrase: Optional[OnSizeErrorPhrase] = None
        self.not_on_size_error_phrase: Optional[NotOnSizeErrorPhrase] = None

    def _populate(self) -> None:
        ctx = self.ctx
        self.on_size_error_phrase = self._phrase(
            OnSizeErrorPhrase, ctx.onSizeErrorPhrase()
        )
        self.not_on_size_error_phrase = self._phrase(
            NotOnSizeErrorPhrase, ctx.notOnSizeErrorPhrase()
        )

    def _operand_value_stmts(self, ctxs) -> List:
        """Build a ValueStmt per ``identifier | literal`` operand ctx."""
        return [self.create_value_stmt(c.identifier(), c.literal()) for c in ctxs]

    def _rounded_call(self, ctx) -> _RoundedCall:
        """Build a :class:`_RoundedCall` from an ``identifier ROUNDED?`` ctx."""
        call = None
        ident = ctx.identifier()
        if ident is not None:
            call = self.create_call(ident)
        rounded = getattr(ctx, "ROUNDED", lambda: None)() is not None
        return _RoundedCall(call, rounded)


class AddStatement(_ArithmeticStatementBase):
    """``ADD``: TO / TO GIVING / CORRESPONDING forms."""

    statement_type = StatementTypeEnum.ADD

    class AddType(Enum):
        TO = "TO"
        TO_GIVING = "TO_GIVING"
        CORRESPONDING = "CORRESPONDING"

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.add_type: Optional[AddStatement.AddType] = None
        self.from_value_stmts: List = []  # addends (addFrom); TO + TO GIVING
        self.to_targets: List[_RoundedCall] = []  # addTo (TO)
        self.to_value_stmts: List = []  # addToGiving (TO GIVING)
        self.giving_targets: List[_RoundedCall] = []  # addGiving (TO GIVING)
        self.corresponding_from_call = None  # identifier (CORRESPONDING)
        self.corresponding_to_call = None  # addTo identifier (CORRESPONDING)

    def _populate(self) -> None:
        super()._populate()
        ctx = self.ctx
        if ctx.addToStatement() is not None:
            self.add_type = AddStatement.AddType.TO
            sub = ctx.addToStatement()
            self.from_value_stmts = self._operand_value_stmts(_as_list(sub.addFrom()))
            self.to_targets = [self._rounded_call(t) for t in _as_list(sub.addTo())]
        elif ctx.addToGivingStatement() is not None:
            self.add_type = AddStatement.AddType.TO_GIVING
            sub = ctx.addToGivingStatement()
            self.from_value_stmts = self._operand_value_stmts(_as_list(sub.addFrom()))
            self.to_value_stmts = self._operand_value_stmts(
                _as_list(sub.addToGiving())
            )
            self.giving_targets = [
                self._rounded_call(g) for g in _as_list(sub.addGiving())
            ]
        elif ctx.addCorrespondingStatement() is not None:
            self.add_type = AddStatement.AddType.CORRESPONDING
            sub = ctx.addCorrespondingStatement()
            if sub.identifier() is not None:
                self.corresponding_from_call = self.create_call(sub.identifier())
            to = sub.addTo()  # singular in the CORRESPONDING form
            if to is not None and to.identifier() is not None:
                self.corresponding_to_call = self.create_call(to.identifier())


class SubtractStatement(_ArithmeticStatementBase):
    """``SUBTRACT``: FROM / FROM GIVING / CORRESPONDING forms."""

    statement_type = StatementTypeEnum.SUBTRACT

    class SubtractType(Enum):
        FROM = "FROM"
        FROM_GIVING = "FROM_GIVING"
        CORRESPONDING = "CORRESPONDING"

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.subtract_type: Optional[SubtractStatement.SubtractType] = None
        self.subtrahend_value_stmts: List = []  # subtractSubtrahend
        self.from_targets: List[_RoundedCall] = []  # subtractMinuend (FROM)
        self.from_value_stmt = None  # subtractMinuendGiving (FROM GIVING)
        self.giving_targets: List[_RoundedCall] = []  # subtractGiving (FROM GIVING)
        self.corresponding_subtrahend_call = None  # qualifiedDataName (CORR)
        self.corresponding_from_target: Optional[_RoundedCall] = None

    def _populate(self) -> None:
        super()._populate()
        ctx = self.ctx
        if ctx.subtractFromStatement() is not None:
            self.subtract_type = SubtractStatement.SubtractType.FROM
            sub = ctx.subtractFromStatement()
            self.subtrahend_value_stmts = self._operand_value_stmts(
                _as_list(sub.subtractSubtrahend())
            )
            self.from_targets = [
                self._rounded_call(m) for m in _as_list(sub.subtractMinuend())
            ]
        elif ctx.subtractFromGivingStatement() is not None:
            self.subtract_type = SubtractStatement.SubtractType.FROM_GIVING
            sub = ctx.subtractFromGivingStatement()
            self.subtrahend_value_stmts = self._operand_value_stmts(
                _as_list(sub.subtractSubtrahend())
            )
            mg = sub.subtractMinuendGiving()  # singular
            if mg is not None:
                self.from_value_stmt = self.create_value_stmt(
                    mg.identifier(), mg.literal()
                )
            self.giving_targets = [
                self._rounded_call(g) for g in _as_list(sub.subtractGiving())
            ]
        elif ctx.subtractCorrespondingStatement() is not None:
            self.subtract_type = SubtractStatement.SubtractType.CORRESPONDING
            sub = ctx.subtractCorrespondingStatement()
            qdn = sub.qualifiedDataName()
            if qdn is not None:
                self.corresponding_subtrahend_call = self.create_call(qdn)
            mc = sub.subtractMinuendCorresponding()  # qualifiedDataName ROUNDED?
            if mc is not None:
                q = mc.qualifiedDataName()
                call = self.create_call(q) if q is not None else None
                self.corresponding_from_target = _RoundedCall(
                    call, mc.ROUNDED() is not None
                )


class MultiplyStatement(_ArithmeticStatementBase):
    """``MULTIPLY``: BY / BY GIVING forms."""

    statement_type = StatementTypeEnum.MULTIPLY

    class MultiplyType(Enum):
        BY = "BY"
        BY_GIVING = "BY_GIVING"

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.multiply_type: Optional[MultiplyStatement.MultiplyType] = None
        self.operand_value_stmt = None  # MULTIPLY <operand>
        self.by_targets: List[_RoundedCall] = []  # multiplyRegularOperand (BY)
        self.giving_operand_value_stmt = None  # multiplyGivingOperand (BY GIVING)
        self.giving_targets: List[_RoundedCall] = []  # multiplyGivingResult

    def _populate(self) -> None:
        super()._populate()
        ctx = self.ctx
        self.operand_value_stmt = self.create_value_stmt(
            ctx.identifier(), ctx.literal()
        )
        if ctx.multiplyRegular() is not None:
            self.multiply_type = MultiplyStatement.MultiplyType.BY
            reg = ctx.multiplyRegular()
            self.by_targets = [
                self._rounded_call(op) for op in _as_list(reg.multiplyRegularOperand())
            ]
        elif ctx.multiplyGiving() is not None:
            self.multiply_type = MultiplyStatement.MultiplyType.BY_GIVING
            g = ctx.multiplyGiving()
            gop = g.multiplyGivingOperand()  # singular
            if gop is not None:
                self.giving_operand_value_stmt = self.create_value_stmt(
                    gop.identifier(), gop.literal()
                )
            self.giving_targets = [
                self._rounded_call(r) for r in _as_list(g.multiplyGivingResult())
            ]


class DivideStatement(_ArithmeticStatementBase):
    """``DIVIDE``: INTO / INTO GIVING / BY GIVING forms (+ optional REMAINDER)."""

    statement_type = StatementTypeEnum.DIVIDE

    class DivideType(Enum):
        INTO = "INTO"
        INTO_GIVING = "INTO_GIVING"
        BY_GIVING = "BY_GIVING"

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.divide_type: Optional[DivideStatement.DivideType] = None
        self.operand_value_stmt = None  # DIVIDE <operand>
        self.into_targets: List[_RoundedCall] = []  # divideInto (INTO)
        self.into_value_stmt = None  # INTO <operand> (INTO GIVING)
        self.by_value_stmt = None  # BY <operand> (BY GIVING)
        self.giving_targets: List[_RoundedCall] = []  # divideGiving (GIVING)
        self.remainder_call = None  # REMAINDER identifier

    def _populate(self) -> None:
        super()._populate()
        ctx = self.ctx
        self.operand_value_stmt = self.create_value_stmt(
            ctx.identifier(), ctx.literal()
        )
        if ctx.divideIntoStatement() is not None:
            self.divide_type = DivideStatement.DivideType.INTO
            sub = ctx.divideIntoStatement()
            self.into_targets = [
                self._rounded_call(i) for i in _as_list(sub.divideInto())
            ]
        elif ctx.divideIntoGivingStatement() is not None:
            self.divide_type = DivideStatement.DivideType.INTO_GIVING
            sub = ctx.divideIntoGivingStatement()
            self.into_value_stmt = self.create_value_stmt(
                sub.identifier(), sub.literal()
            )
            self.giving_targets = self._divide_givings(sub)
        elif ctx.divideByGivingStatement() is not None:
            self.divide_type = DivideStatement.DivideType.BY_GIVING
            sub = ctx.divideByGivingStatement()
            self.by_value_stmt = self.create_value_stmt(
                sub.identifier(), sub.literal()
            )
            self.giving_targets = self._divide_givings(sub)
        rem = ctx.divideRemainder()
        if rem is not None and rem.identifier() is not None:
            self.remainder_call = self.create_call(rem.identifier())

    def _divide_givings(self, sub_ctx) -> List[_RoundedCall]:
        """The ``divideGivingPhrase`` -> ``divideGiving`` targets (INTO/BY GIVING)."""
        phrase = sub_ctx.divideGivingPhrase()
        if phrase is None:
            return []
        return [self._rounded_call(dg) for dg in _as_list(phrase.divideGiving())]


class ComputeStatement(_ArithmeticStatementBase):
    """``COMPUTE <stores> = <arithmetic expression>``."""

    statement_type = StatementTypeEnum.COMPUTE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.stores: List[_RoundedCall] = []  # computeStore targets
        self.arithmetic_expression = None  # ArithmeticValueStmt

    def _populate(self) -> None:
        super()._populate()
        ctx = self.ctx
        self.stores = [self._rounded_call(s) for s in _as_list(ctx.computeStore())]
        expr = ctx.arithmeticExpression()
        if expr is not None:
            self.arithmetic_expression = self.create_arithmetic_value_stmt(expr)


# --- file I/O verbs (Phase C2) --------------------------------------------

def _as_list(maybe):
    """Normalise an ANTLR accessor result to a list (single ctx or list)."""
    if maybe is None:
        return []
    if isinstance(maybe, list):
        return maybe
    return [maybe]


def _has(ctx, token_name: str) -> bool:
    """Return ``True`` if the named ANTLR typed token is present on ``ctx``."""
    accessor = getattr(ctx, token_name, None)
    return callable(accessor) and accessor() is not None


class OpenStatement(_StatementBase):
    """``OPEN INPUT/OUTPUT/IO/EXTEND <files>``: collects the file-name calls."""

    statement_type = StatementTypeEnum.OPEN

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.file_calls: List = []

    def _populate(self) -> None:
        # File names sit under per-mode phrases (openInputStatement / openOutput
        # / openIO / openExtendStatement), each wrapping a context that holds
        # fileName(). Walk the ctx for FileNameContext nodes (robust to nesting).
        stack = [self.ctx]
        seen = set()
        while stack:
            node = stack.pop()
            if node is None or id(node) in seen:
                continue
            seen.add(id(node))
            if type(node).__name__ == "FileNameContext":
                self.file_calls.append(self.create_call(node))
                continue
            for i in range(getattr(node, "getChildCount", lambda: 0)()):
                stack.append(node.getChild(i))


class CloseStatement(_StatementBase):
    """``CLOSE <files>``: collects the file-name calls."""

    statement_type = StatementTypeEnum.CLOSE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.file_calls: List = []

    def _populate(self) -> None:
        ctx = self.ctx
        for close_file in _as_list(getattr(ctx, "closeFile", lambda: [])()):
            for file_name in _as_list(getattr(close_file, "fileName", lambda: [])()):
                self.file_calls.append(self.create_call(file_name))


class ReadStatement(_StatementBase):
    """``READ <file> [NEXT] [RECORD] [INTO <id>] [WITH <lock>] [KEY <id>] ...``.

    Ports ``ScopeImpl.addReadStatement`` + ``ReadStatementImpl.addInto/addKey/
    addWith``. Note ``next_record`` is keyed on the ``RECORD`` token (matching
    Java), not ``NEXT``.
    """

    statement_type = StatementTypeEnum.READ

    class WithType(Enum):
        KEPT_LOCK = "KEPT_LOCK"
        NO_LOCK = "NO_LOCK"
        WAIT = "WAIT"

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.file_call = None
        self.into_call = None
        self.next_record = False
        self.key_call = None
        self.with_type: Optional[ReadStatement.WithType] = None
        self.invalid_key_phrase: Optional[InvalidKeyPhrase] = None
        self.not_invalid_key_phrase: Optional[NotInvalidKeyPhrase] = None
        self.at_end_phrase: Optional[AtEndPhrase] = None
        self.not_at_end_phrase: Optional[NotAtEndPhrase] = None

    def _populate(self) -> None:
        ctx = self.ctx
        file_name = getattr(ctx, "fileName", lambda: None)()
        if file_name is not None:
            self.file_call = self.create_call(file_name)
        # Java keys nextRecord off ctx.RECORD(), not ctx.NEXT().
        if getattr(ctx, "RECORD", lambda: None)() is not None:
            self.next_record = True
        into_ctx = getattr(ctx, "readInto", lambda: None)()
        if into_ctx is not None:
            identifier = getattr(into_ctx, "identifier", lambda: None)()
            if identifier is not None:
                self.into_call = self.create_call(identifier)
        with_ctx = getattr(ctx, "readWith", lambda: None)()
        if with_ctx is not None:
            self.with_type = self._with_type(with_ctx)
        key_ctx = getattr(ctx, "readKey", lambda: None)()
        if key_ctx is not None:
            qdn = getattr(key_ctx, "qualifiedDataName", lambda: None)()
            if qdn is not None:
                self.key_call = self.create_call(qdn)
        self.invalid_key_phrase = self._phrase(InvalidKeyPhrase, ctx.invalidKeyPhrase())
        self.not_invalid_key_phrase = self._phrase(
            NotInvalidKeyPhrase, ctx.notInvalidKeyPhrase()
        )
        self.at_end_phrase = self._phrase(AtEndPhrase, ctx.atEndPhrase())
        self.not_at_end_phrase = self._phrase(NotAtEndPhrase, ctx.notAtEndPhrase())

    @staticmethod
    def _with_type(ctx) -> "Optional[ReadStatement.WithType]":
        # readWith: WITH? ((KEPT | NO) LOCK | WAIT)
        if getattr(ctx, "KEPT", lambda: None)() is not None:
            return ReadStatement.WithType.KEPT_LOCK
        if getattr(ctx, "NO", lambda: None)() is not None:
            return ReadStatement.WithType.NO_LOCK
        if getattr(ctx, "WAIT", lambda: None)() is not None:
            return ReadStatement.WithType.WAIT
        return None


class WriteStatement(_StatementBase):
    """``WRITE <record> [FROM <id|lit>] [advancing] [AT END-OF-PAGE ...] ...``.

    Ports ``ScopeImpl.addWriteStatement`` + ``WriteStatementImpl.addFrom /
    addAdvancingPhrase``. FROM is a ValueStmt (may be a literal); the advancing
    phrase decomposes into position (BEFORE/AFTER) + type (PAGE/LINES/MNEMONIC).
    """

    statement_type = StatementTypeEnum.WRITE

    class PositionType(Enum):
        BEFORE = "BEFORE"
        AFTER = "AFTER"

    class AdvancingType(Enum):
        PAGE = "PAGE"
        LINES = "LINES"
        MNEMONIC = "MNEMONIC"

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.record_call = None
        self.from_value_stmt = None
        self.advancing_position: Optional[WriteStatement.PositionType] = None
        self.advancing_type: Optional[WriteStatement.AdvancingType] = None
        self.advancing_lines_value_stmt = None  # writeAdvancingLines count
        self.advancing_mnemonic_call = None  # writeAdvancingMnemonic
        self.at_end_of_page_phrase: Optional[AtEndOfPagePhrase] = None
        self.not_at_end_of_page_phrase: Optional[NotAtEndOfPagePhrase] = None
        self.invalid_key_phrase: Optional[InvalidKeyPhrase] = None
        self.not_invalid_key_phrase: Optional[NotInvalidKeyPhrase] = None

    def _populate(self) -> None:
        ctx = self.ctx
        record = getattr(ctx, "recordName", lambda: None)()
        if record is not None:
            self.record_call = self.create_call(record)
        from_ctx = getattr(ctx, "writeFromPhrase", lambda: None)()
        if from_ctx is not None:
            self.from_value_stmt = self.create_value_stmt(
                getattr(from_ctx, "identifier", lambda: None)(),
                getattr(from_ctx, "literal", lambda: None)(),
            )
        adv = getattr(ctx, "writeAdvancingPhrase", lambda: None)()
        if adv is not None:
            self._populate_advancing(adv)
        self.at_end_of_page_phrase = self._phrase(
            AtEndOfPagePhrase, ctx.writeAtEndOfPagePhrase()
        )
        self.not_at_end_of_page_phrase = self._phrase(
            NotAtEndOfPagePhrase, ctx.writeNotAtEndOfPagePhrase()
        )
        self.invalid_key_phrase = self._phrase(InvalidKeyPhrase, ctx.invalidKeyPhrase())
        self.not_invalid_key_phrase = self._phrase(
            NotInvalidKeyPhrase, ctx.notInvalidKeyPhrase()
        )

    def _populate_advancing(self, adv) -> None:
        # writeAdvancingPhrase: (BEFORE | AFTER) ADVANCING? (page|lines|mnemonic)
        if getattr(adv, "BEFORE", lambda: None)() is not None:
            self.advancing_position = WriteStatement.PositionType.BEFORE
        elif getattr(adv, "AFTER", lambda: None)() is not None:
            self.advancing_position = WriteStatement.PositionType.AFTER
        page = getattr(adv, "writeAdvancingPage", lambda: None)()
        lines = getattr(adv, "writeAdvancingLines", lambda: None)()
        mnemonic = getattr(adv, "writeAdvancingMnemonic", lambda: None)()
        if page is not None:
            self.advancing_type = WriteStatement.AdvancingType.PAGE
        elif lines is not None:
            self.advancing_type = WriteStatement.AdvancingType.LINES
            self.advancing_lines_value_stmt = self.create_value_stmt(
                getattr(lines, "identifier", lambda: None)(),
                getattr(lines, "literal", lambda: None)(),
            )
        elif mnemonic is not None:
            self.advancing_type = WriteStatement.AdvancingType.MNEMONIC
            mn = getattr(mnemonic, "mnemonicName", lambda: None)()
            if mn is not None:
                self.advancing_mnemonic_call = self.create_call(mn)


class RewriteStatement(_StatementBase):
    """``REWRITE <record> [FROM <id>] [INVALID KEY ...]``."""

    statement_type = StatementTypeEnum.REWRITE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.record_call = None
        self.from_call = None
        self.invalid_key_phrase: Optional[InvalidKeyPhrase] = None
        self.not_invalid_key_phrase: Optional[NotInvalidKeyPhrase] = None

    def _populate(self) -> None:
        ctx = self.ctx
        record = getattr(ctx, "recordName", lambda: None)()
        if record is not None:
            self.record_call = self.create_call(record)
        from_ctx = getattr(ctx, "rewriteFrom", lambda: None)()
        if from_ctx is not None:
            identifier = getattr(from_ctx, "identifier", lambda: None)()
            if identifier is not None:
                self.from_call = self.create_call(identifier)
        self.invalid_key_phrase = self._phrase(InvalidKeyPhrase, ctx.invalidKeyPhrase())
        self.not_invalid_key_phrase = self._phrase(
            NotInvalidKeyPhrase, ctx.notInvalidKeyPhrase()
        )


class DeleteStatement(_StatementBase):
    """``DELETE <file> [INVALID KEY ...]``."""

    statement_type = StatementTypeEnum.DELETE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.file_call = None
        self.invalid_key_phrase: Optional[InvalidKeyPhrase] = None
        self.not_invalid_key_phrase: Optional[NotInvalidKeyPhrase] = None

    def _populate(self) -> None:
        ctx = self.ctx
        file_name = getattr(ctx, "fileName", lambda: None)()
        if file_name is not None:
            self.file_call = self.create_call(file_name)
        self.invalid_key_phrase = self._phrase(InvalidKeyPhrase, ctx.invalidKeyPhrase())
        self.not_invalid_key_phrase = self._phrase(
            NotInvalidKeyPhrase, ctx.notInvalidKeyPhrase()
        )


class StartStatement(_StatementBase):
    """``START <file> KEY <rel> <id> [INVALID KEY ...]``.

    Ports ``ScopeImpl.addStartStatement`` + ``StartStatementImpl.addKey``. The
    KeyType mirrors Java (GREATER_OR_EQUAL / GREATER / EQUAL; ``NOT LESS`` maps
    to GREATER_OR_EQUAL).
    """

    statement_type = StatementTypeEnum.START

    class KeyType(Enum):
        GREATER_OR_EQUAL = "GREATER_OR_EQUAL"
        GREATER = "GREATER"
        EQUAL = "EQUAL"

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.file_call = None
        self.key_type: Optional[StartStatement.KeyType] = None
        self.key_comparison_call = None
        self.invalid_key_phrase: Optional[InvalidKeyPhrase] = None
        self.not_invalid_key_phrase: Optional[NotInvalidKeyPhrase] = None

    def _populate(self) -> None:
        ctx = self.ctx
        file_name = getattr(ctx, "fileName", lambda: None)()
        if file_name is not None:
            self.file_call = self.create_call(file_name)
        key_ctx = getattr(ctx, "startKey", lambda: None)()
        if key_ctx is not None:
            self.key_type = self._key_type(key_ctx)
            qdn = getattr(key_ctx, "qualifiedDataName", lambda: None)()
            if qdn is not None:
                self.key_comparison_call = self.create_call(qdn)
        self.invalid_key_phrase = self._phrase(InvalidKeyPhrase, ctx.invalidKeyPhrase())
        self.not_invalid_key_phrase = self._phrase(
            NotInvalidKeyPhrase, ctx.notInvalidKeyPhrase()
        )

    @staticmethod
    def _key_type(ctx) -> "Optional[StartStatement.KeyType]":
        def tok(name):
            return getattr(ctx, name, lambda: None)() is not None

        if tok("MORETHANOREQUAL"):
            return StartStatement.KeyType.GREATER_OR_EQUAL
        if tok("GREATER") and tok("EQUAL"):
            return StartStatement.KeyType.GREATER_OR_EQUAL
        if tok("NOT") and (tok("LESSTHANCHAR") or tok("LESS")):
            return StartStatement.KeyType.GREATER_OR_EQUAL
        if tok("MORETHANCHAR") or tok("GREATER"):
            return StartStatement.KeyType.GREATER
        if tok("EQUAL") or tok("EQUALCHAR"):
            return StartStatement.KeyType.EQUAL
        return None


# --- more common verbs (Phase C2 cont.) -----------------------------------

class CallStatement(_StatementBase):
    """``CALL <program> [USING <args>]``: subprogram call + USING arguments."""

    statement_type = StatementTypeEnum.CALL

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.program_value_stmt = None
        self.using_calls: List = []
        self.giving_call = None
        self.on_overflow_phrase: Optional[OnOverflowPhrase] = None
        self.on_exception_clause: Optional[OnExceptionClause] = None
        self.not_on_exception_clause: Optional[NotOnExceptionClause] = None

    def _populate(self) -> None:
        ctx = self.ctx
        ids = _as_list(getattr(ctx, "identifier", lambda: [])())
        lits = _as_list(getattr(ctx, "literal", lambda: [])())
        name_ctx = ids[0] if ids else (lits[0] if lits else None)
        if name_ctx is not None:
            self.program_value_stmt = self.create_value_stmt(name_ctx)
        # USING parameters nest under callUsingPhrase -> callUsingParameter
        # -> callByReference/Value/Content -> identifier. Walk the USING subtree
        # for IdentifierContext nodes (robust to that nesting).
        roots = _as_list(getattr(ctx, "callUsingPhrase", lambda: [])())
        stack = list(roots)
        seen = set()
        while stack:
            node = stack.pop()
            if node is None or id(node) in seen:
                continue
            seen.add(id(node))
            if type(node).__name__ == "IdentifierContext":
                self.using_calls.append(self.create_call(node))
                continue
            for i in range(getattr(node, "getChildCount", lambda: 0)()):
                stack.append(node.getChild(i))
        # GIVING / RETURNING <id>.
        giving_phrase = getattr(ctx, "callGivingPhrase", lambda: None)()
        if giving_phrase is not None:
            giving_ident = getattr(giving_phrase, "identifier", lambda: None)()
            if giving_ident is not None:
                self.giving_call = self.create_call(giving_ident)
        self.on_overflow_phrase = self._phrase(OnOverflowPhrase, ctx.onOverflowPhrase())
        self.on_exception_clause = self._phrase(
            OnExceptionClause, ctx.onExceptionClause()
        )
        self.not_on_exception_clause = self._phrase(
            NotOnExceptionClause, ctx.notOnExceptionClause()
        )


class SetStatement(_StatementBase):
    """``SET <data> TO <value>`` / ``SET <data> UP|DOWN BY <value>``."""

    statement_type = StatementTypeEnum.SET

    class SetType(Enum):
        SET_TO = "SET_TO"
        SET_UP = "SET_UP"
        SET_DOWN = "SET_DOWN"

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.set_type: Optional[SetStatement.SetType] = None
        self.receiving_calls: List = []
        self.value_stmt = None

    def _populate(self) -> None:
        ctx = self.ctx
        text = ctx.getText().upper()
        tos = _as_list(getattr(ctx, "setToStatement", lambda: [])())
        updown = _as_list(getattr(ctx, "setUpDownByStatement", lambda: [])())
        if updown and not tos:
            # UP BY / DOWN BY is a typed token on the setUpDownByStatement ctx,
            # not a substring (avoids false-positive on names containing "DOWN").
            has_down = updown[0].DOWN() is not None if hasattr(updown[0], "DOWN") else "DOWN" in text
            self.set_type = SetStatement.SetType.SET_DOWN if has_down else SetStatement.SetType.SET_UP
        else:
            self.set_type = SetStatement.SetType.SET_TO
        # receiving identifiers live under setTo() within either form.
        for grp in tos + updown:
            for set_to in _as_list(getattr(grp, "setTo", lambda: [])()):
                for identifier in _as_list(getattr(set_to, "identifier", lambda: [])()):
                    self.receiving_calls.append(self.create_call(identifier))
        # value: SET TO <value> (setToValue) or UP/DOWN BY <value> (setByValue).
        for acc in ("setToValue", "setByValue"):
            for value_ctx in _as_list(getattr(ctx, acc, lambda: [])()):
                vals = _as_list(getattr(value_ctx, "identifier", lambda: [])()) or _as_list(
                    getattr(value_ctx, "literal", lambda: [])()
                )
                if vals:
                    self.value_stmt = self.create_value_stmt(vals[0])
                    break
            if self.value_stmt is not None:
                break


class EvaluateStatement(_StatementBase):
    """``EVALUATE <subject> WHEN ... [WHEN OTHER ...]``.

    Owns each ``WHEN`` branch (``EvaluateWhenPhrase``) and the optional
    ``WHEN OTHER`` branch (``EvaluateWhenOther``) so their nested statements do
    not leak to the paragraph. Per-``WHEN`` condition detail is deferred.
    """

    statement_type = StatementTypeEnum.EVALUATE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.subject_value_stmt = None
        self.when_phrases: List[EvaluateWhenPhrase] = []
        self.when_other: Optional[EvaluateWhenOther] = None

    @property
    def when_count(self) -> int:
        """Total number of ``WHEN`` clauses across all branches."""
        return sum(p.when_count for p in self.when_phrases)

    def _populate(self) -> None:
        ctx = self.ctx
        select = getattr(ctx, "evaluateSelect", lambda: None)()
        if select is not None:
            for acc in ("condition", "arithmeticExpression", "identifier", "literal"):
                vals = _as_list(getattr(select, acc, lambda: [])())
                if vals:
                    self.subject_value_stmt = self.create_value_stmt(vals[0])
                    break
        for phrase_ctx in _as_list(ctx.evaluateWhenPhrase()):
            phrase = self._build_phrase_scope(EvaluateWhenPhrase, phrase_ctx)
            phrase.when_count = len(_as_list(phrase_ctx.evaluateWhen()))
            self.when_phrases.append(phrase)
        self.when_other = self._phrase(EvaluateWhenOther, ctx.evaluateWhenOther())


class InitializeStatement(_StatementBase):
    """``INITIALIZE <data-items>``: the data items to initialize."""

    statement_type = StatementTypeEnum.INITIALIZE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.data_item_calls: List = []

    def _populate(self) -> None:
        for identifier in _as_list(getattr(self.ctx, "identifier", lambda: [])()):
            self.data_item_calls.append(self.create_call(identifier))


# --- string / table verbs (Phase C2 cont.) -------------------------------

class StringStatement(_StatementBase):
    """``STRING ... INTO <id>``: the INTO receiving call (phrase detail deferred)."""

    statement_type = StatementTypeEnum.STRING

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.into_call = None
        self.sending_calls: List = []
        self.on_overflow_phrase: Optional[OnOverflowPhrase] = None
        self.not_on_overflow_phrase: Optional[NotOnOverflowPhrase] = None

    def _populate(self) -> None:
        ctx = self.ctx
        into = getattr(ctx, "stringIntoPhrase", lambda: None)()
        if into is not None:
            for identifier in _as_list(getattr(into, "identifier", lambda: [])()):
                self.into_call = self.create_call(identifier)
                break
        for sending in _as_list(getattr(ctx, "stringSending", lambda: [])()):
            for identifier in _as_list(getattr(sending, "identifier", lambda: [])()):
                self.sending_calls.append(self.create_call(identifier))
        self.on_overflow_phrase = self._phrase(OnOverflowPhrase, ctx.onOverflowPhrase())
        self.not_on_overflow_phrase = self._phrase(
            NotOnOverflowPhrase, ctx.notOnOverflowPhrase()
        )


class UnstringStatement(_StatementBase):
    """``UNSTRING ... INTO <ids>``: the INTO receiving calls (minimal)."""

    statement_type = StatementTypeEnum.UNSTRING

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.into_calls: List = []
        self.on_overflow_phrase: Optional[OnOverflowPhrase] = None
        self.not_on_overflow_phrase: Optional[NotOnOverflowPhrase] = None

    def _populate(self) -> None:
        ctx = self.ctx
        # INTO targets nest under unstringIntoPhrase -> unstringInto -> identifier.
        for phrase in _as_list(getattr(ctx, "unstringIntoPhrase", lambda: [])()):
            for into in _as_list(getattr(phrase, "unstringInto", lambda: [])()):
                for identifier in _as_list(getattr(into, "identifier", lambda: [])()):
                    self.into_calls.append(self.create_call(identifier))
        self.on_overflow_phrase = self._phrase(OnOverflowPhrase, ctx.onOverflowPhrase())
        self.not_on_overflow_phrase = self._phrase(
            NotOnOverflowPhrase, ctx.notOnOverflowPhrase()
        )


class InspectStatement(_StatementBase):
    """``INSPECT <id> ...``: the inspected data item (phrase detail deferred)."""

    statement_type = StatementTypeEnum.INSPECT

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.data_item_call = None

    def _populate(self) -> None:
        for identifier in _as_list(getattr(self.ctx, "identifier", lambda: [])()):
            self.data_item_call = self.create_call(identifier)
            break


class SearchStatement(_StatementBase):
    """``SEARCH <table> [AT END ...] [WHEN <cond> <stmts>] ...``."""

    statement_type = StatementTypeEnum.SEARCH

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.data_call = None
        self.at_end_phrase: Optional[AtEndPhrase] = None
        self.when_phrases: List[SearchWhenPhrase] = []

    def _populate(self) -> None:
        ctx = self.ctx
        for qdn in _as_list(getattr(ctx, "qualifiedDataName", lambda: [])()):
            self.data_call = self.create_call(qdn)
            break
        self.at_end_phrase = self._phrase(AtEndPhrase, ctx.atEndPhrase())
        # Each WHEN <condition> <statements> becomes its own phrase scope.
        for when_ctx in _as_list(ctx.searchWhen()):
            phrase = self._build_phrase_scope(SearchWhenPhrase, when_ctx)
            cond_ctx = getattr(when_ctx, "condition", lambda: None)()
            if cond_ctx is not None:
                phrase.condition = self.create_condition_value_stmt(cond_ctx)
            self.when_phrases.append(phrase)


# --- statement-list containers: IF Then/Else, PERFORM inline body, AT END -----
#
# These are phrase :class:`Scope` subclasses. Because each phrase scope is built
# and registered before the dispatch visitor recurses into it, ``find_scope``
# returns the phrase for nested verbs, so they register on the phrase (not the
# enclosing paragraph) — matching proleap, where these phrases implement Scope.


class _StatementListContainer(Scope):
    """A phrase scope that owns an ordered group of nested statements.

    Bases for IF Then/Else, PERFORM inline body, and AT END (and similar)
    phrases. Extending :class:`Scope` means the dispatch visitor's
    ``find_scope`` returns the phrase for the nested verbs, so they register on
    the phrase via :meth:`Scope.register_statement` instead of leaking up to the
    enclosing paragraph — matching proleap, where these phrases implement
    ``Scope``.
    """

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.next_sentence = False


class Then(_StatementListContainer):
    """The THEN branch of an IF statement."""


class Else(_StatementListContainer):
    """The ELSE branch of an IF statement."""


class AtEndPhrase(_StatementListContainer):
    """The ``AT END`` phrase of a statement (e.g. RETURN / READ / SEARCH).

    Owns the statements executed at end-of-file; they register here rather than
    on the enclosing paragraph.
    """


class NotAtEndPhrase(_StatementListContainer):
    """The ``NOT AT END`` phrase of a statement (e.g. READ)."""


class InvalidKeyPhrase(_StatementListContainer):
    """The ``INVALID KEY`` phrase (READ / WRITE / REWRITE / DELETE / START)."""


class NotInvalidKeyPhrase(_StatementListContainer):
    """The ``NOT INVALID KEY`` phrase (READ / WRITE / REWRITE / DELETE / START)."""


class AtEndOfPagePhrase(_StatementListContainer):
    """The ``AT END-OF-PAGE`` phrase of a WRITE statement."""


class NotAtEndOfPagePhrase(_StatementListContainer):
    """The ``NOT AT END-OF-PAGE`` phrase of a WRITE statement."""


class OnSizeErrorPhrase(_StatementListContainer):
    """The ``ON SIZE ERROR`` phrase of an arithmetic statement."""


class NotOnSizeErrorPhrase(_StatementListContainer):
    """The ``NOT ON SIZE ERROR`` phrase of an arithmetic statement."""


class OnExceptionClause(_StatementListContainer):
    """The ``ON EXCEPTION`` clause (CALL / DISPLAY / ACCEPT / RECEIVE / SEND)."""


class NotOnExceptionClause(_StatementListContainer):
    """The ``NOT ON EXCEPTION`` clause (CALL / DISPLAY / ACCEPT / RECEIVE / SEND)."""


class OnOverflowPhrase(_StatementListContainer):
    """The ``ON OVERFLOW`` phrase (CALL / STRING / UNSTRING)."""


class NotOnOverflowPhrase(_StatementListContainer):
    """The ``NOT ON OVERFLOW`` phrase (CALL / STRING / UNSTRING)."""


class PerformInlineStatement(_StatementListContainer):
    """The inline body of ``PERFORM ... <statements> END-PERFORM``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        # performType: TIMES / VARYING / UNTIL / WHILE (clause detail deferred).
        self.perform_type = None


class SearchWhenPhrase(_StatementListContainer):
    """One ``WHEN <condition> <statements>`` branch of a SEARCH.

    Owns the branch statements (no leak to the paragraph) and carries the
    branch condition.
    """

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.condition = None  # ConditionValueStmt


class EvaluateWhenPhrase(_StatementListContainer):
    """One ``WHEN <conditions> <statements>`` branch of an EVALUATE.

    Wraps an ``evaluateWhenPhrase`` (``evaluateWhen+ statement*``): owns the
    branch statements; the per-``evaluateWhen`` condition detail is deferred.
    """

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.when_count = 0  # number of evaluateWhen clauses in this branch


class EvaluateWhenOther(_StatementListContainer):
    """The ``WHEN OTHER <statements>`` branch of an EVALUATE."""


# --- SORT / MERGE ----------------------------------------------------------

class SortStatement(_StatementBase):
    """``SORT <file> ON <keys> USING <files> GIVING <files> | INPUT/OUTPUT PROCEDURE``."""

    statement_type = StatementTypeEnum.SORT

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.file_call = None
        self.key_calls: List = []
        self.using_calls: List = []  # input files (SORT USING)
        self.giving_calls: List = []  # output files (SORT GIVING)
        self.input_procedure_calls: List = []
        self.output_procedure_calls: List = []

    def _populate(self) -> None:
        ctx = self.ctx
        file_name = ctx.fileName()
        if file_name is not None:
            self.file_call = self.create_call(file_name)
        for on_key in _as_list(ctx.sortOnKeyClause()):
            for qdn in _as_list(on_key.qualifiedDataName()):
                self.key_calls.append(self.create_call(qdn))
        for using in _as_list(ctx.sortUsing()):
            for fn in _as_list(using.fileName()):
                self.using_calls.append(self.create_call(fn))
        for giving_phrase in _as_list(ctx.sortGivingPhrase()):
            for giving in _as_list(giving_phrase.sortGiving()):
                gfn = giving.fileName()
                if gfn is not None:
                    self.giving_calls.append(self.create_call(gfn))
        input_phrase = ctx.sortInputProcedurePhrase()
        if input_phrase is not None:
            self.input_procedure_calls.append(self.create_call(input_phrase.procedureName()))
            through = input_phrase.sortInputThrough()
            if through is not None and through.procedureName() is not None:
                self.input_procedure_calls.append(self.create_call(through.procedureName()))
        output_phrase = ctx.sortOutputProcedurePhrase()
        if output_phrase is not None:
            self.output_procedure_calls.append(self.create_call(output_phrase.procedureName()))
            through = output_phrase.sortOutputThrough()
            if through is not None and through.procedureName() is not None:
                self.output_procedure_calls.append(self.create_call(through.procedureName()))


class MergeStatement(_StatementBase):
    """``MERGE <file> ON <keys> USING <files> OUTPUT PROCEDURE | GIVING <files>``."""

    statement_type = StatementTypeEnum.MERGE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.file_call = None
        self.key_calls: List = []
        self.using_calls: List = []
        self.giving_calls: List = []
        self.output_procedure_calls: List = []

    def _populate(self) -> None:
        ctx = self.ctx
        file_name = ctx.fileName()
        if file_name is not None:
            self.file_call = self.create_call(file_name)
        for on_key in _as_list(ctx.mergeOnKeyClause()):
            for qdn in _as_list(on_key.qualifiedDataName()):
                self.key_calls.append(self.create_call(qdn))
        for using in _as_list(ctx.mergeUsing()):
            for fn in _as_list(using.fileName()):
                self.using_calls.append(self.create_call(fn))
        for giving_phrase in _as_list(ctx.mergeGivingPhrase()):
            for giving in _as_list(giving_phrase.mergeGiving()):
                gfn = giving.fileName()
                if gfn is not None:
                    self.giving_calls.append(self.create_call(gfn))
        output_phrase = ctx.mergeOutputProcedurePhrase()
        if output_phrase is not None:
            self.output_procedure_calls.append(self.create_call(output_phrase.procedureName()))
            through = output_phrase.mergeOutputThrough()
            if through is not None and through.procedureName() is not None:
                self.output_procedure_calls.append(self.create_call(through.procedureName()))


# --- ALTER -----------------------------------------------------------------

class ProceedTo(CobolDivisionElement):
    """One ``ALTER <source> TO PROCEED TO <target>`` clause."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.source_call = None
        self.target_call = None


class AlterStatement(_StatementBase):
    """``ALTER <para> TO PROCEED TO <para>``: one or more proceed-to clauses."""

    statement_type = StatementTypeEnum.ALTER

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.proceed_tos: List[ProceedTo] = []

    def _populate(self) -> None:
        for ptc in _as_list(self.ctx.alterProceedTo()):
            result = self._get_element(ptc)
            if result is None:
                result = ProceedTo(self.program_unit, ptc)
                names = _as_list(ptc.procedureName())
                if len(names) >= 1:
                    result.source_call = self.create_call(names[0])
                if len(names) >= 2:
                    result.target_call = self.create_call(names[1])
                self._register(result)
            self.proceed_tos.append(result)


# --- CANCEL / RETURN / RELEASE --------------------------------------------

class CancelStatement(_StatementBase):
    """``CANCEL <program> ...``: the cancelled subprogram references."""

    statement_type = StatementTypeEnum.CANCEL

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.calls: List = []
        self.value_stmts: List = []

    def _populate(self) -> None:
        for cc in _as_list(self.ctx.cancelCall()):
            # Name may be a libraryName/identifier (a Call) or a literal.
            for ident in _as_list(getattr(cc, "identifier", lambda: [])()):
                self.calls.append(self.create_call(ident))
                break
            else:
                for lit in _as_list(getattr(cc, "literal", lambda: [])()):
                    self.value_stmts.append(self.create_value_stmt(lit))
                    break


class ReturnStatement(_StatementBase):
    """``RETURN <file> [INTO <id>] [AT END <stmts>]`` (used with SORT)."""

    statement_type = StatementTypeEnum.RETURN

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.file_call = None
        self.into_call = None
        self.at_end_phrase: Optional[AtEndPhrase] = None
        self.not_at_end_phrase: Optional[NotAtEndPhrase] = None

    def _populate(self) -> None:
        ctx = self.ctx
        file_name = ctx.fileName()
        if file_name is not None:
            self.file_call = self.create_call(file_name)
        into_ctx = getattr(ctx, "returnInto", lambda: None)()
        if into_ctx is not None:
            for qdn in _as_list(getattr(into_ctx, "qualifiedDataName", lambda: [])()):
                self.into_call = self.create_call(qdn)
                break
        self.at_end_phrase = self._phrase(AtEndPhrase, ctx.atEndPhrase())
        self.not_at_end_phrase = self._phrase(NotAtEndPhrase, ctx.notAtEndPhrase())


class ReleaseStatement(_StatementBase):
    """``RELEASE <record> [FROM <id>]`` (used with SORT)."""

    statement_type = StatementTypeEnum.RELEASE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.record_call = None
        self.from_call = None

    def _populate(self) -> None:
        ctx = self.ctx
        record = ctx.recordName()
        if record is not None:
            self.record_call = self.create_call(record)
        for qdn in _as_list(getattr(ctx, "qualifiedDataName", lambda: [])()):
            self.from_call = self.create_call(qdn)
            break


# --- EXEC (embedded CICS / SQL) + remaining rare verbs --------------------
#
# All 14 verbs now carry typed clause decomposition matching Java (Wave 5).
# EXEC verbs extract the untagged body text via TagUtils-style stripping.

# ---------------------------------------------------------------------------
# EXEC CICS / SQL / SQLIMS — body text extraction
# ---------------------------------------------------------------------------

def _untagged_text(ctx, tag: str, end_tag: str = "}") -> str:
    """Extract body text from EXEC-line tokens, stripping tags (Java TagUtils.getUntaggedText)."""
    from ...preprocessor.constants import EXEC_CICS_TAG, EXEC_END_TAG, EXEC_SQL_TAG, EXEC_SQLIMS_TAG

    tag_map = {"EXEC_CICS": EXEC_CICS_TAG, "EXEC_SQL": EXEC_SQL_TAG,
               "EXEC_SQLIMS": EXEC_SQLIMS_TAG}
    real_tag = tag_map.get(tag, tag)
    token_name = {"EXEC_CICS": "EXECCICSLINE", "EXEC_SQL": "EXECSQLLINE",
                   "EXEC_SQLIMS": "EXECSQLIMSLINE"}.get(tag, "")
    if not token_name:
        return ctx.getText()
    tokens_getter = getattr(ctx, token_name, None)
    if tokens_getter is None or not callable(tokens_getter):
        return ctx.getText()
    token_nodes = tokens_getter()
    if not token_nodes:
        return ""
    parts = []
    for tn in (token_nodes if isinstance(token_nodes, list) else [token_nodes]):
        text = tn.getText() if hasattr(tn, "getText") else str(tn)
        for t in (real_tag, end_tag):
            text = text.replace(t, "")
        parts.append(text.strip())
    return " ".join(parts).strip()


class ExecCicsStatement(_StatementBase):
    statement_type = StatementTypeEnum.EXEC_CICS

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.exec_cics_text: str = ""

    def _populate(self):
        self.exec_cics_text = _untagged_text(self.ctx, "EXEC_CICS")


class ExecSqlStatement(_StatementBase):
    statement_type = StatementTypeEnum.EXEC_SQL

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.exec_sql_text: str = ""

    def _populate(self):
        self.exec_sql_text = _untagged_text(self.ctx, "EXEC_SQL")


class ExecSqlImsStatement(_StatementBase):
    statement_type = StatementTypeEnum.EXEC_SQLIMS

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.exec_sql_ims_text: str = ""

    def _populate(self):
        self.exec_sql_ims_text = _untagged_text(self.ctx, "EXEC_SQLIMS")


# ---------------------------------------------------------------------------
# DISABLE / ENABLE — typed MCS control
# ---------------------------------------------------------------------------

class DisableType(Enum):
    INPUT = "INPUT"
    INPUT_OUTPUT = "INPUT_OUTPUT"
    OUTPUT = "OUTPUT"


class DisableStatement(_StatementBase):
    statement_type = StatementTypeEnum.DISABLE

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.disable_type: Optional[DisableType] = None
        self.terminal: bool = False
        self.communication_description_call = None
        self.key_value_stmt = None

    def _populate(self):
        ctx = self.ctx
        # Detect type via direct ANTLR accessors (matching Java: ctx.INPUT() != null, etc.)
        if ctx.I_O() is not None:
            self.disable_type = DisableType.INPUT_OUTPUT
        elif ctx.INPUT() is not None:
            self.disable_type = DisableType.INPUT
        elif ctx.OUTPUT() is not None:
            self.disable_type = DisableType.OUTPUT
        self.terminal = ctx.TERMINAL() is not None
        cd = ctx.cdName()
        if cd is not None:
            self.communication_description_call = self.create_call(cd)
        self.key_value_stmt = self.create_value_stmt(ctx.identifier(), ctx.literal())


class EnableType(Enum):
    INPUT = "INPUT"
    INPUT_OUTPUT = "INPUT_OUTPUT"
    OUTPUT = "OUTPUT"


class EnableStatement(_StatementBase):
    statement_type = StatementTypeEnum.ENABLE

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.enable_type: Optional[EnableType] = None
        self.terminal: bool = False
        self.communication_description_call = None
        self.key_value_stmt = None

    def _populate(self):
        ctx = self.ctx
        if ctx.INPUT() is not None:
            self.enable_type = EnableType.INPUT
        elif ctx.I_O() is not None:
            self.enable_type = EnableType.INPUT_OUTPUT
        elif ctx.OUTPUT() is not None:
            self.enable_type = EnableType.OUTPUT
        self.terminal = ctx.TERMINAL() is not None
        cd = ctx.cdName()
        if cd is not None:
            self.communication_description_call = self.create_call(cd)
        self.key_value_stmt = self.create_value_stmt(ctx.identifier(), ctx.literal())


# ---------------------------------------------------------------------------
# ENTRY — alternate entry point
# ---------------------------------------------------------------------------

class EntryStatement(_StatementBase):
    statement_type = StatementTypeEnum.ENTRY

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.entry_value_stmt = None
        self.using_calls: List = []

    def _populate(self):
        ctx = self.ctx
        self.entry_value_stmt = self.create_value_stmt(ctx.literal())
        for ident_ctx in _as_list(ctx.identifier()):
            self.using_calls.append(self.create_call(ident_ctx))


# ---------------------------------------------------------------------------
# EXHIBIT — display with operands
# ---------------------------------------------------------------------------

class ExhibitOperand(CobolDivisionElement):
    """One ``identifier | literal`` operand of EXHIBIT."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.operand_value_stmt = None


class ExhibitStatement(_StatementBase):
    statement_type = StatementTypeEnum.EXHIBIT

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.named: bool = False
        self.changed: bool = False
        self.operands: List[ExhibitOperand] = []

    def _populate(self):
        ctx = self.ctx
        self.named = _has(ctx, "NAMED")
        self.changed = _has(ctx, "CHANGED")
        for op_ctx in _as_list(ctx.exhibitOperand()):
            operand = self._get_element(op_ctx)
            if operand is None:
                operand = ExhibitOperand(self.program_unit, op_ctx)
                operand.operand_value_stmt = self.create_value_stmt(
                    op_ctx.identifier(), op_ctx.literal()
                )
                self._register(operand)
            self.operands.append(operand)


# ---------------------------------------------------------------------------
# GENERATE / INITIATE / TERMINATE / PURGE — report-writer and MCS verbs
# ---------------------------------------------------------------------------

class GenerateStatement(_StatementBase):
    statement_type = StatementTypeEnum.GENERATE

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.report_description_call = None

    def _populate(self):
        rn = self.ctx.reportName()
        if rn is not None:
            self.report_description_call = self.create_call(rn)


class InitiateStatement(_StatementBase):
    statement_type = StatementTypeEnum.INITIATE

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.report_calls: List = []

    def _populate(self):
        for rn in _as_list(self.ctx.reportName()):
            self.report_calls.append(self.create_call(rn))


class TerminateStatement(_StatementBase):
    statement_type = StatementTypeEnum.TERMINATE

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.report_call = None

    def _populate(self):
        rn = self.ctx.reportName()
        if rn is not None:
            self.report_call = self.create_call(rn)


class PurgeStatement(_StatementBase):
    statement_type = StatementTypeEnum.PURGE

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.communication_description_entry_calls: List = []

    def _populate(self):
        for cd in _as_list(self.ctx.cdName()):
            self.communication_description_entry_calls.append(self.create_call(cd))


# ---------------------------------------------------------------------------
# RECEIVE — FROM / INTO forms with sub-clause decomposition
# ---------------------------------------------------------------------------

class ReceiveType(Enum):
    FROM = "FROM"
    INTO = "INTO"


# -- RECEIVE FROM sub-models -------------------------------------------------

class ReceiveBefore(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.time_value_stmt = None


class ReceiveFrom(CobolDivisionElement):
    class FromType(Enum):
        THREAD = "THREAD"
        LAST_THREAD = "LAST_THREAD"
        ANY_THREAD = "ANY_THREAD"

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.from_type: Optional[ReceiveFrom.FromType] = None
        self.thread_call = None


class ReceiveWith(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.no_wait = True


class ReceiveThread(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.thread_in_call = None


class ReceiveSize(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.size_value_stmt = None


class ReceiveStatus(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.status_call = None


class ReceiveFromStatement(CobolDivisionElement):
    """``dataName FROM receiveFrom (before|with|thread|size|status)*``."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_call = None
        self.from_: Optional[ReceiveFrom] = None
        self.before: Optional[ReceiveBefore] = None
        self.with_: Optional[ReceiveWith] = None
        self.thread: Optional[ReceiveThread] = None
        self.size: Optional[ReceiveSize] = None
        self.status: Optional[ReceiveStatus] = None

    def _populate(self):
        ctx = self.ctx
        self.data_call = self.create_call(ctx.dataName())
        # from
        rf = ctx.receiveFrom()
        if rf is not None:
            self.from_ = self._get_element(rf)
            if self.from_ is None:
                ft = ReceiveFrom(self.program_unit, rf)
                if _has(rf, "LAST"):
                    ft.from_type = ReceiveFrom.FromType.LAST_THREAD
                elif _has(rf, "ANY"):
                    ft.from_type = ReceiveFrom.FromType.ANY_THREAD
                else:
                    ft.from_type = ReceiveFrom.FromType.THREAD
                ft.thread_call = self.create_call(rf.dataName())
                self._register(ft)
                self.from_ = ft
        # before
        for bc in _as_list(ctx.receiveBefore()):
            self.before = self._get_element(bc)
            if self.before is None:
                bt = ReceiveBefore(self.program_unit, bc)
                bt.time_value_stmt = self.create_value_stmt(
                    bc.identifier(), bc.numericLiteral()
                )
                self._register(bt)
                self.before = bt
        # with
        for wc in _as_list(ctx.receiveWith()):
            self.with_ = self._get_element(wc)
            if self.with_ is None:
                wt = ReceiveWith(self.program_unit, wc)
                self._register(wt)
                self.with_ = wt
        # thread
        for tc in _as_list(ctx.receiveThread()):
            self.thread = self._get_element(tc)
            if self.thread is None:
                tt = ReceiveThread(self.program_unit, tc)
                tt.thread_in_call = self.create_call(tc.dataName())
                self._register(tt)
                self.thread = tt
        # size
        for sc in _as_list(ctx.receiveSize()):
            self.size = self._get_element(sc)
            if self.size is None:
                st = ReceiveSize(self.program_unit, sc)
                st.size_value_stmt = self.create_value_stmt(
                    sc.numericLiteral(), sc.identifier()
                )
                self._register(st)
                self.size = st
        # status
        for stc in _as_list(ctx.receiveStatus()):
            self.status = self._get_element(stc)
            if self.status is None:
                stt = ReceiveStatus(self.program_unit, stc)
                ident = stc.identifier()
                if ident is not None:
                    stt.status_call = self.create_call(ident)
                self._register(stt)
                self.status = stt


# -- RECEIVE INTO sub-models -------------------------------------------------

class ReceiveIntoType(Enum):
    MESSAGE = "MESSAGE"
    SEGMENT = "SEGMENT"


class ReceiveNoData(CobolDivisionElement):
    """``NO DATA statement*`` phrase scope for RECEIVE INTO."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)


class ReceiveWithData(CobolDivisionElement):
    """``WITH DATA statement*`` phrase scope for RECEIVE INTO."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)


class ReceiveIntoStatement(CobolDivisionElement):
    """``cdName (MESSAGE|SEGMENT) INTO? id [NO DATA] [WITH DATA]``."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.communication_description_call = None
        self.receive_into_type: Optional[ReceiveIntoType] = None
        self.into_call = None
        self.no_data: Optional[ReceiveNoData] = None
        self.with_data: Optional[ReceiveWithData] = None

    def _populate(self):
        ctx = self.ctx
        cd = ctx.cdName()
        if cd is not None:
            self.communication_description_call = self.create_call(cd)
        if _has(ctx, "MESSAGE"):
            self.receive_into_type = ReceiveIntoType.MESSAGE
        elif _has(ctx, "SEGMENT"):
            self.receive_into_type = ReceiveIntoType.SEGMENT
        ident = ctx.identifier()
        if ident is not None:
            self.into_call = self.create_call(ident)
        nd = ctx.receiveNoData()
        if nd is not None:
            result = self._get_element(nd)
            if result is None:
                result = ReceiveNoData(self.program_unit, nd)
                self._register(result)
            self.no_data = result
        wd = ctx.receiveWithData()
        if wd is not None:
            result = self._get_element(wd)
            if result is None:
                result = ReceiveWithData(self.program_unit, wd)
                self._register(result)
            self.with_data = result


class ReceiveStatement(_StatementBase):
    statement_type = StatementTypeEnum.RECEIVE

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.receive_type: Optional[ReceiveType] = None
        self.receive_from_statement: Optional[ReceiveFromStatement] = None
        self.receive_into_statement: Optional[ReceiveIntoStatement] = None
        self.on_exception_clause: Optional[OnExceptionClause] = None
        self.not_on_exception_clause: Optional[NotOnExceptionClause] = None

    def _populate(self):
        ctx = self.ctx
        rfs = ctx.receiveFromStatement()
        ris = ctx.receiveIntoStatement()
        if rfs is not None:
            self.receive_type = ReceiveType.FROM
            result = self._get_element(rfs)
            if result is None:
                result = ReceiveFromStatement(self.program_unit, rfs)
                result._populate()
                self._register(result)
            self.receive_from_statement = result
        elif ris is not None:
            self.receive_type = ReceiveType.INTO
            result = self._get_element(ris)
            if result is None:
                result = ReceiveIntoStatement(self.program_unit, ris)
                result._populate()
                self._register(result)
            self.receive_into_statement = result
        self.on_exception_clause = self._phrase(OnExceptionClause, ctx.onExceptionClause())
        self.not_on_exception_clause = self._phrase(
            NotOnExceptionClause, ctx.notOnExceptionClause()
        )


# ---------------------------------------------------------------------------
# SEND — SYNC / ASYNC forms with sub-clause decomposition
# ---------------------------------------------------------------------------

class SendType(Enum):
    ASYNC = "ASYNC"
    SYNC = "SYNC"


class SendAsync(CobolDivisionElement):
    """``TO (TOP|BOTTOM) identifier``."""

    class AsyncType(Enum):
        TOP = "TOP"
        BOTTOM = "BOTTOM"

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.async_type: Optional[SendAsync.AsyncType] = None
        self.data_description_entry_call = None


class SendFrom(CobolDivisionElement):
    """``FROM identifier``."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.from_call = None


class SendWithType(Enum):
    CALL = "CALL"
    EGI = "EGI"
    EMI = "EMI"
    ESI = "ESI"


class SendWith(CobolDivisionElement):
    """``WITH (EGI|EMI|ESI|identifier)``."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.with_call = None
        self.with_type: Optional[SendWithType] = None


class SendAdvancingType(Enum):
    PAGE = "PAGE"
    LINES = "LINES"
    MNEMONIC = "MNEMONIC"


class SendPositionType(Enum):
    BEFORE = "BEFORE"
    AFTER = "AFTER"


class SendAdvancingLines(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.lines_value_stmt = None


class SendAdvancingMnemonic(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.mnemonic_call = None


class SendAdvancing(CobolDivisionElement):
    """``(BEFORE|AFTER) ADVANCING? (PAGE|LINES|MNEMONIC)``."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.advancing_type: Optional[SendAdvancingType] = None
        self.position_type: Optional[SendPositionType] = None
        self.advancing_lines: Optional[SendAdvancingLines] = None
        self.advancing_mnemonic: Optional[SendAdvancingMnemonic] = None


class SendSync(CobolDivisionElement):
    """``(id|lit) [FROM] [WITH] [REPLACING] [advancing]``."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.receiving_program_value_stmt = None
        self.from_: Optional[SendFrom] = None
        self.with_: Optional[SendWith] = None
        self.replacing: bool = False
        self.advancing: Optional[SendAdvancing] = None


class SendStatement(_StatementBase):
    statement_type = StatementTypeEnum.SEND

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.send_type: Optional[SendType] = None
        self.sync: Optional[SendSync] = None
        self.async_: Optional[SendAsync] = None
        self.on_exception_clause: Optional[OnExceptionClause] = None
        self.not_on_exception_clause: Optional[NotOnExceptionClause] = None

    def _populate(self):
        ctx = self.ctx
        sync_ctx = ctx.sendStatementSync()
        async_ctx = ctx.sendStatementAsync()
        if sync_ctx is not None:
            self.send_type = SendType.SYNC
            sync = self._get_element(sync_ctx)
            if sync is None:
                sync = SendSync(self.program_unit, sync_ctx)
                sync.receiving_program_value_stmt = self.create_value_stmt(
                    sync_ctx.identifier(), sync_ctx.literal()
                )
                # FROM
                from_ctx = sync_ctx.sendFromPhrase()
                if from_ctx is not None:
                    sf = SendFrom(self.program_unit, from_ctx)
                    ident = from_ctx.identifier()
                    if ident is not None:
                        sf.from_call = self.create_call(ident)
                    self._register(sf)
                    sync.from_ = sf
                # WITH
                with_ctx = sync_ctx.sendWithPhrase()
                if with_ctx is not None:
                    sw = SendWith(self.program_unit, with_ctx)
                    if _has(with_ctx, "EGI"):
                        sw.with_type = SendWithType.EGI
                    elif _has(with_ctx, "EMI"):
                        sw.with_type = SendWithType.EMI
                    elif _has(with_ctx, "ESI"):
                        sw.with_type = SendWithType.ESI
                    elif with_ctx.identifier() is not None:
                        sw.with_type = SendWithType.CALL
                        sw.with_call = self.create_call(with_ctx.identifier())
                    self._register(sw)
                    sync.with_ = sw
                # REPLACING
                if sync_ctx.sendReplacingPhrase() is not None:
                    sync.replacing = True
                # ADVANCING
                adv_ctx = sync_ctx.sendAdvancingPhrase()
                if adv_ctx is not None:
                    sa = SendAdvancing(self.program_unit, adv_ctx)
                    if _has(adv_ctx, "AFTER"):
                        sa.position_type = SendPositionType.AFTER
                    elif _has(adv_ctx, "BEFORE"):
                        sa.position_type = SendPositionType.BEFORE
                    page = adv_ctx.sendAdvancingPage()
                    lines = adv_ctx.sendAdvancingLines()
                    mnemonic = adv_ctx.sendAdvancingMnemonic()
                    if page is not None:
                        sa.advancing_type = SendAdvancingType.PAGE
                    elif lines is not None:
                        sa.advancing_type = SendAdvancingType.LINES
                        al = SendAdvancingLines(self.program_unit, lines)
                        al.lines_value_stmt = self.create_value_stmt(
                            lines.identifier(), lines.literal()
                        )
                        self._register(al)
                        sa.advancing_lines = al
                    elif mnemonic is not None:
                        sa.advancing_type = SendAdvancingType.MNEMONIC
                        am = SendAdvancingMnemonic(self.program_unit, mnemonic)
                        mn = mnemonic.mnemonicName()
                        if mn is not None:
                            am.mnemonic_call = self.create_call(mn)
                        self._register(am)
                        sa.advancing_mnemonic = am
                    self._register(sa)
                    sync.advancing = sa
                self._register(sync)
            self.sync = sync
        elif async_ctx is not None:
            self.send_type = SendType.ASYNC
            sa = self._get_element(async_ctx)
            if sa is None:
                sa = SendAsync(self.program_unit, async_ctx)
                if _has(async_ctx, "TOP"):
                    sa.async_type = SendAsync.AsyncType.TOP
                elif _has(async_ctx, "BOTTOM"):
                    sa.async_type = SendAsync.AsyncType.BOTTOM
                ident = async_ctx.identifier()
                if ident is not None:
                    sa.data_description_entry_call = self.create_call(ident)
                self._register(sa)
            self.async_ = sa
        self.on_exception_clause = self._phrase(OnExceptionClause, ctx.onExceptionClause())
        self.not_on_exception_clause = self._phrase(
            NotOnExceptionClause, ctx.notOnExceptionClause()
        )


# ---------------------------------------------------------------------------
# USE — AFTER / DEBUG forms with sub-clause decomposition
# ---------------------------------------------------------------------------

class UseType(Enum):
    AFTER = "AFTER"
    DEBUG = "DEBUG"


class UseAfterOn(CobolDivisionElement):
    """The ``ON`` clause of USE AFTER: ``INPUT|OUTPUT|I_O|EXTEND|fileName+``."""

    class AfterOnType(Enum):
        INPUT = "INPUT"
        OUTPUT = "OUTPUT"
        INPUT_OUTPUT = "INPUT_OUTPUT"
        EXTEND = "EXTEND"
        FILE = "FILE"

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.after_on_type: Optional[UseAfterOn.AfterOnType] = None
        self.file_calls: List = []


class UseAfterStatement(CobolDivisionElement):
    """``GLOBAL? AFTER STANDARD? (EXCEPTION|ERROR) PROCEDURE ON? useAfterOn``."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.global_: bool = False
        self.after_on: Optional[UseAfterOn] = None


class DebugOnType(Enum):
    ALL_PROCEDURES = "ALL_PROCEDURES"
    ALL_REFERENCES = "ALL_REFERENCES"
    FILE = "FILE"
    PROCEDURE = "PROCEDURE"


class UseDebugOn(CobolDivisionElement):
    """One ``ON`` target of USE FOR DEBUGGING."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.debug_on_type: Optional[DebugOnType] = None
        self.on_call = None


class UseDebugStatement(CobolDivisionElement):
    """``FOR? DEBUGGING ON? useDebugOn+``."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.debug_ons: List[UseDebugOn] = []


class UseStatement(_StatementBase):
    statement_type = StatementTypeEnum.USE

    def __init__(self, program_unit, scope, ctx):
        super().__init__(program_unit, scope, ctx)
        self.use_type: Optional[UseType] = None
        self.use_after_statement: Optional[UseAfterStatement] = None
        self.use_debug_statement: Optional[UseDebugStatement] = None

    def _populate(self):
        ctx = self.ctx
        after_ctx = ctx.useAfterClause()
        debug_ctx = ctx.useDebugClause()
        if after_ctx is not None:
            self.use_type = UseType.AFTER
            ua = self._get_element(after_ctx)
            if ua is None:
                ua = UseAfterStatement(self.program_unit, after_ctx)
                ua.global_ = _has(after_ctx, "GLOBAL")
                # after ON
                on_ctx = after_ctx.useAfterOn()
                if on_ctx is not None:
                    ao = self._get_element(on_ctx)
                    if ao is None:
                        ao = UseAfterOn(self.program_unit, on_ctx)
                        # type
                        if on_ctx.fileName():
                            ao.after_on_type = UseAfterOn.AfterOnType.FILE
                        elif _has(on_ctx, "INPUT") and _has(on_ctx, "I_O"):
                            ao.after_on_type = UseAfterOn.AfterOnType.INPUT_OUTPUT
                        elif _has(on_ctx, "INPUT"):
                            ao.after_on_type = UseAfterOn.AfterOnType.INPUT
                        elif _has(on_ctx, "OUTPUT"):
                            ao.after_on_type = UseAfterOn.AfterOnType.OUTPUT
                        elif _has(on_ctx, "EXTEND"):
                            ao.after_on_type = UseAfterOn.AfterOnType.EXTEND
                        # files
                        for fn in _as_list(on_ctx.fileName()):
                            ao.file_calls.append(self.create_call(fn))
                        self._register(ao)
                    ua.after_on = ao
                self._register(ua)
            self.use_after_statement = ua
        elif debug_ctx is not None:
            self.use_type = UseType.DEBUG
            ud = self._get_element(debug_ctx)
            if ud is None:
                ud = UseDebugStatement(self.program_unit, debug_ctx)
                for on_ctx in _as_list(debug_ctx.useDebugOn()):
                    do = UseDebugOn(self.program_unit, on_ctx)
                    if _has(on_ctx, "PROCEDURES"):
                        do.debug_on_type = DebugOnType.ALL_PROCEDURES
                    elif _has(on_ctx, "REFERENCES"):
                        do.debug_on_type = DebugOnType.ALL_REFERENCES
                        ident = on_ctx.identifier()
                        if ident is not None:
                            do.on_call = self.create_call(ident)
                    elif on_ctx.procedureName() is not None:
                        do.debug_on_type = DebugOnType.PROCEDURE
                        do.on_call = self.create_call(on_ctx.procedureName())
                    elif on_ctx.fileName() is not None:
                        do.debug_on_type = DebugOnType.FILE
                        do.on_call = self.create_call(on_ctx.fileName())
                    self._register(do)
                    ud.debug_ons.append(do)
                self._register(ud)
            self.use_debug_statement = ud

