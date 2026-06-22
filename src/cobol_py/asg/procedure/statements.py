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


# --- arithmetic (typed + ctx retained; operand decomposition deferred) -----

class _ArithmeticStatementBase(_StatementBase):
    """Base for ADD/SUBTRACT/MULTIPLY/DIVIDE/COMPUTE.

    Operand decomposition is deferred, but the ``ON SIZE ERROR`` /
    ``NOT ON SIZE ERROR`` phrases are owned so their nested statements do not
    leak to the enclosing paragraph.
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


class AddStatement(_ArithmeticStatementBase):
    statement_type = StatementTypeEnum.ADD


class SubtractStatement(_ArithmeticStatementBase):
    statement_type = StatementTypeEnum.SUBTRACT


class MultiplyStatement(_ArithmeticStatementBase):
    statement_type = StatementTypeEnum.MULTIPLY


class DivideStatement(_ArithmeticStatementBase):
    statement_type = StatementTypeEnum.DIVIDE


class ComputeStatement(_ArithmeticStatementBase):
    statement_type = StatementTypeEnum.COMPUTE


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
    """``READ <file> [INTO <id>] [NEXT RECORD] [INVALID KEY ...] [AT END ...]``."""

    statement_type = StatementTypeEnum.READ

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.file_call = None
        self.into_call = None
        self.next_record = False
        self.invalid_key_phrase: Optional[InvalidKeyPhrase] = None
        self.not_invalid_key_phrase: Optional[NotInvalidKeyPhrase] = None
        self.at_end_phrase: Optional[AtEndPhrase] = None
        self.not_at_end_phrase: Optional[NotAtEndPhrase] = None

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
        self.invalid_key_phrase = self._phrase(InvalidKeyPhrase, ctx.invalidKeyPhrase())
        self.not_invalid_key_phrase = self._phrase(
            NotInvalidKeyPhrase, ctx.notInvalidKeyPhrase()
        )
        self.at_end_phrase = self._phrase(AtEndPhrase, ctx.atEndPhrase())
        self.not_at_end_phrase = self._phrase(NotAtEndPhrase, ctx.notAtEndPhrase())


class WriteStatement(_StatementBase):
    """``WRITE <record> [FROM <id>] [AT END-OF-PAGE ...] [INVALID KEY ...]``."""

    statement_type = StatementTypeEnum.WRITE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.record_call = None
        self.from_call = None
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
            identifier = getattr(from_ctx, "identifier", lambda: None)()
            if identifier is not None:
                self.from_call = self.create_call(identifier)
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


class RewriteStatement(_StatementBase):
    """``REWRITE <record> [INVALID KEY ...]``."""

    statement_type = StatementTypeEnum.REWRITE

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.record_call = None
        self.invalid_key_phrase: Optional[InvalidKeyPhrase] = None
        self.not_invalid_key_phrase: Optional[NotInvalidKeyPhrase] = None

    def _populate(self) -> None:
        ctx = self.ctx
        record = getattr(ctx, "recordName", lambda: None)()
        if record is not None:
            self.record_call = self.create_call(record)
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
    """``START <file> KEY ... [INVALID KEY ...]``."""

    statement_type = StatementTypeEnum.START

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


# --- more common verbs (Phase C2 cont.) -----------------------------------

class CallStatement(_StatementBase):
    """``CALL <program> [USING <args>]``: subprogram call + USING arguments."""

    statement_type = StatementTypeEnum.CALL

    def __init__(self, program_unit, scope, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit, scope, ctx)
        self.program_value_stmt = None
        self.using_calls: List = []
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
# These verbs retain their ctx but their internal clauses are not decomposed.
# They complete coverage of StatementTypeEnum: every COBOL verb now produces a
# typed statement node (matching proleap, which builds a Statement for each).

class ExecCicsStatement(_StatementBase):
    statement_type = StatementTypeEnum.EXEC_CICS


class ExecSqlStatement(_StatementBase):
    statement_type = StatementTypeEnum.EXEC_SQL


class ExecSqlImsStatement(_StatementBase):
    statement_type = StatementTypeEnum.EXEC_SQLIMS


class EnableStatement(_StatementBase):
    statement_type = StatementTypeEnum.ENABLE


class DisableStatement(_StatementBase):
    statement_type = StatementTypeEnum.DISABLE


class ReceiveStatement(_StatementBase):
    statement_type = StatementTypeEnum.RECEIVE


class SendStatement(_StatementBase):
    statement_type = StatementTypeEnum.SEND


class ExhibitStatement(_StatementBase):
    statement_type = StatementTypeEnum.EXHIBIT


class GenerateStatement(_StatementBase):
    statement_type = StatementTypeEnum.GENERATE


class InitiateStatement(_StatementBase):
    statement_type = StatementTypeEnum.INITIATE


class TerminateStatement(_StatementBase):
    statement_type = StatementTypeEnum.TERMINATE


class PurgeStatement(_StatementBase):
    statement_type = StatementTypeEnum.PURGE


class UseStatement(_StatementBase):
    statement_type = StatementTypeEnum.USE


class EntryStatement(_StatementBase):
    statement_type = StatementTypeEnum.ENTRY

