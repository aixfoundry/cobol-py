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
from .division import Statement, StatementTypeEnum


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
            # inline body deferred (nested statements attach to the scope)


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

    def _populate(self) -> None:
        for operand_ctx in self.ctx.displayOperand():
            operand = self._get_element(operand_ctx)
            if operand is None:
                operand = DisplayOperand(self.program_unit, operand_ctx)
                operand.operand_value_stmt = self.create_value_stmt(
                    operand_ctx.identifier(), operand_ctx.literal()
                )
                self._register(operand)
            self.operands.append(operand)


# --- IF --------------------------------------------------------------------

class IfStatement(_StatementBase):
    statement_type = StatementTypeEnum.IF

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.condition = None  # ConditionValueStmt

    def _populate(self) -> None:
        condition_ctx = self.ctx.condition()
        if condition_ctx is not None:
            self.condition = self.create_condition_value_stmt(condition_ctx)
        # Then/Else containers deferred; nested statements attach to the scope.


# --- ACCEPT / GOTO ---------------------------------------------------------

class AcceptStatement(_StatementBase):
    statement_type = StatementTypeEnum.ACCEPT

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.receiving_call = None

    def _populate(self) -> None:
        identifier_ctx = self.ctx.identifier()
        if identifier_ctx is not None:
            self.receiving_call = self.create_call(identifier_ctx)


class GoToStatement(_StatementBase):
    statement_type = StatementTypeEnum.GO_TO

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.calls: List = []

    def _populate(self) -> None:
        for procedure_ctx in self.ctx.procedureName():
            self.calls.append(self.create_call(procedure_ctx))


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


# --- arithmetic (typed + ctx retained; operand decomposition deferred) -----

class AddStatement(_StatementBase):
    statement_type = StatementTypeEnum.ADD


class SubtractStatement(_StatementBase):
    statement_type = StatementTypeEnum.SUBTRACT


class MultiplyStatement(_StatementBase):
    statement_type = StatementTypeEnum.MULTIPLY


class DivideStatement(_StatementBase):
    statement_type = StatementTypeEnum.DIVIDE


class ComputeStatement(_StatementBase):
    statement_type = StatementTypeEnum.COMPUTE


# verb-name -> statement class, used by the dispatch visitor.
STATEMENT_CLASSES = {
    "accept": AcceptStatement,
    "add": AddStatement,
    "subtract": SubtractStatement,
    "multiply": MultiplyStatement,
    "divide": DivideStatement,
    "compute": ComputeStatement,
    "if": IfStatement,
    "perform": PerformStatement,
    "goto": GoToStatement,
    "display": DisplayStatement,
    "stop": StopStatement,
    "continue": ContinueStatement,
    "exit": ExitStatement,
    "goback": GobackStatement,
    "move": MoveStatement,
}


# --- file I/O verbs (Phase C2) --------------------------------------------

def _as_list(maybe):
    """Normalise an ANTLR accessor result to a list (single ctx or list)."""
    if maybe is None:
        return []
    if isinstance(maybe, list):
        return maybe
    return [maybe]


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
    """``READ <file> [INTO <id>] [NEXT RECORD]``."""

    statement_type = StatementTypeEnum.READ

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.file_call = None
        self.into_call = None
        self.next_record = False

    def _populate(self) -> None:
        ctx = self.ctx
        file_name = getattr(ctx, "fileName", lambda: None)()
        if file_name is not None:
            self.file_call = self.create_call(file_name)
        if "NEXT" in ctx.getText().upper():
            self.next_record = True
        into_ctx = getattr(ctx, "readInto", lambda: None)()
        if into_ctx is not None:
            identifier = getattr(into_ctx, "identifier", lambda: None)()
            if identifier is not None:
                self.into_call = self.create_call(identifier)


class WriteStatement(_StatementBase):
    """``WRITE <record> [FROM <id>]``."""

    statement_type = StatementTypeEnum.WRITE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.record_call = None
        self.from_call = None

    def _populate(self) -> None:
        record = getattr(self.ctx, "recordName", lambda: None)()
        if record is not None:
            self.record_call = self.create_call(record)
        from_ctx = getattr(self.ctx, "writeFromPhrase", lambda: None)()
        if from_ctx is not None:
            identifier = getattr(from_ctx, "identifier", lambda: None)()
            if identifier is not None:
                self.from_call = self.create_call(identifier)


class RewriteStatement(_StatementBase):
    """``REWRITE <record>``."""

    statement_type = StatementTypeEnum.REWRITE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.record_call = None

    def _populate(self) -> None:
        record = getattr(self.ctx, "recordName", lambda: None)()
        if record is not None:
            self.record_call = self.create_call(record)


class DeleteStatement(_StatementBase):
    """``DELETE <file>``."""

    statement_type = StatementTypeEnum.DELETE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.file_call = None

    def _populate(self) -> None:
        file_name = getattr(self.ctx, "fileName", lambda: None)()
        if file_name is not None:
            self.file_call = self.create_call(file_name)


class StartStatement(_StatementBase):
    """``START <file> KEY ...``."""

    statement_type = StatementTypeEnum.START

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.file_call = None

    def _populate(self) -> None:
        file_name = getattr(self.ctx, "fileName", lambda: None)()
        if file_name is not None:
            self.file_call = self.create_call(file_name)


# --- more common verbs (Phase C2 cont.) -----------------------------------

class CallStatement(_StatementBase):
    """``CALL <program> [USING <args>]``: subprogram call + USING arguments."""

    statement_type = StatementTypeEnum.CALL

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.program_value_stmt = None
        self.using_calls: List = []

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
            self.set_type = SetStatement.SetType.SET_DOWN if "DOWN" in text else SetStatement.SetType.SET_UP
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
    """``EVALUATE <subject> WHEN ...``: subject + when-clause count (minimal)."""

    statement_type = StatementTypeEnum.EVALUATE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.subject_value_stmt = None
        self.when_count = 0

    def _populate(self) -> None:
        ctx = self.ctx
        select = getattr(ctx, "evaluateSelect", lambda: None)()
        if select is not None:
            for acc in ("condition", "arithmeticExpression", "identifier", "literal"):
                vals = _as_list(getattr(select, acc, lambda: [])())
                if vals:
                    self.subject_value_stmt = self.create_value_stmt(vals[0])
                    break
        whens = _as_list(getattr(ctx, "evaluateWhen", lambda: [])()) or _as_list(
            getattr(ctx, "evaluateWhenPhrase", lambda: [])()
        )
        self.when_count = len(whens)
        # WHEN-branch statement containers deferred (nested stmts attach to scope).


class InitializeStatement(_StatementBase):
    """``INITIALIZE <data-items>``: the data items to initialize."""

    statement_type = StatementTypeEnum.INITIALIZE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.data_item_calls: List = []

    def _populate(self) -> None:
        for identifier in _as_list(getattr(self.ctx, "identifier", lambda: [])()):
            self.data_item_calls.append(self.create_call(identifier))
