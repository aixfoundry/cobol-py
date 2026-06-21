"""Phase C2: CALL / SET / EVALUATE / INITIALIZE."""

from __future__ import annotations

from cobol_py.asg import (
    CallStatement,
    EvaluateStatement,
    InitializeStatement,
    SetStatement,
    StatementTypeEnum,
)


_SRC = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. T.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-A PIC 9.\n"
    "       01  WS-B PIC 9.\n"
    "       01  WS-C PIC 9.\n"
    "       PROCEDURE DIVISION.\n"
    "       P1.\n"
    "           CALL \"SUB\" USING WS-A WS-B.\n"
    "           SET WS-A TO 5.\n"
    "           SET WS-B UP BY 1.\n"
    "           INITIALIZE WS-A WS-B WS-C.\n"
    "           EVALUATE WS-A\n"
    "              WHEN 1 MOVE 1 TO WS-C\n"
    "              WHEN OTHER MOVE 0 TO WS-C\n"
    "           END-EVALUATE.\n"
)


def _stmts(analyze):
    return analyze(_SRC).compilation_unit.program_unit.procedure_division.get_paragraph("P1").statements


def test_call_program_and_using(analyze):
    call = next(s for s in _stmts(analyze) if isinstance(s, CallStatement))
    assert call.statement_type is StatementTypeEnum.CALL
    assert call.program_value_stmt is not None
    assert {c.unwrap().name for c in call.using_calls} == {"WS-A", "WS-B"}


def test_set_to_and_up(analyze):
    stmts = _stmts(analyze)
    sets = [s for s in stmts if isinstance(s, SetStatement)]
    by_type = {s.set_type: s for s in sets}
    assert SetStatement.SetType.SET_TO in by_type
    assert SetStatement.SetType.SET_UP in by_type
    assert [c.unwrap().name for c in by_type[SetStatement.SetType.SET_TO].receiving_calls] == ["WS-A"]
    assert [c.unwrap().name for c in by_type[SetStatement.SetType.SET_UP].receiving_calls] == ["WS-B"]


def test_initialize_items(analyze):
    init = next(s for s in _stmts(analyze) if isinstance(s, InitializeStatement))
    assert {c.unwrap().name for c in init.data_item_calls} == {"WS-A", "WS-B", "WS-C"}


def test_evaluate_subject_and_whens(analyze):
    ev = next(s for s in _stmts(analyze) if isinstance(s, EvaluateStatement))
    assert ev.subject_value_stmt is not None
    assert ev.when_count >= 1
