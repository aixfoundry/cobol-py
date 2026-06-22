"""Phase C1: core procedure statements."""

from __future__ import annotations

from cobol_py.asg import (
    CallTypeEnum,
    MoveStatement,
    PerformStatement,
    DisplayStatement,
    IfStatement,
    StopStatement,
    ContinueStatement,
    GobackStatement,
    AddStatement,
    StatementTypeEnum,
)


def _program_with(statements_body: str, data_items: str = ""):
    """Helper: build a program whose MAIN paragraph runs the given statements."""
    from cobol_py import CobolParserRunner, CobolSourceFormatEnum
    from cobol_py.params import CobolParserParams

    data = f"       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01  WS-A PIC 9.\n       01  WS-B PIC 9.\n{data_items}" if data_items is not None else ""
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        + data
        + "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        + statements_body
    )
    params = CobolParserParams(format=CobolSourceFormatEnum.FIXED)
    return CobolParserRunner().analyze(src, params)


def test_move_records_receiving_area_calls(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       01  WS-B PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        "           MOVE 5 TO WS-A WS-B.\n"
    )
    # Act
    main = analyze(src).compilation_unit.program_unit.procedure_division.get_paragraph("MAIN")
    stmt = main.statements[0]
    # Assert
    assert isinstance(stmt, MoveStatement)
    assert stmt.statement_type is StatementTypeEnum.MOVE
    assert [c.name for c in stmt.move_to.receiving_area_calls] == ["WS-A", "WS-B"]


def test_perform_resolves_to_paragraph(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        "           PERFORM SUB-PARA.\n"
        "           STOP RUN.\n"
        "       SUB-PARA.\n"
        "           CONTINUE.\n"
    )
    # Act
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    main = pd.get_paragraph("MAIN")
    perform = main.statements[0]
    # Assert
    assert isinstance(perform, PerformStatement)
    call = perform.perform_procedure_statement.calls[0]
    assert call.call_type is CallTypeEnum.PROCEDURE_CALL
    # The call is resolved to the actual SUB-PARA paragraph declaration.
    assert call.paragraph is pd.get_paragraph("SUB-PARA")


def test_display_operands(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        "           DISPLAY 'HELLO' WS-A.\n"
    )
    # Act
    main = analyze(src).compilation_unit.program_unit.procedure_division.get_paragraph("MAIN")
    stmt = main.statements[0]
    # Assert
    assert isinstance(stmt, DisplayStatement)
    assert len(stmt.operands) == 2


def test_if_captures_condition_and_nested_statement(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        "           IF WS-A > 0\n"
        "              DISPLAY 'POS'\n"
        "           END-IF.\n"
    )
    # Act
    main = analyze(src).compilation_unit.program_unit.procedure_division.get_paragraph("MAIN")
    # Assert: IF is the only top-level statement; the nested DISPLAY lives inside
    # the IF's THEN phrase scope (it does not leak to the paragraph).
    assert len(main.statements) == 1
    if_stmt = main.statements[0]
    assert isinstance(if_stmt, IfStatement)
    assert if_stmt.condition is not None
    assert if_stmt.then is not None
    then_stmts = if_stmt.then.statements
    assert len(then_stmts) == 1 and isinstance(then_stmts[0], DisplayStatement)


def test_stop_run_type(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        "           STOP RUN.\n"
    )
    # Act
    main = analyze(src).compilation_unit.program_unit.procedure_division.get_paragraph("MAIN")
    # Assert
    stop = main.statements[0]
    assert isinstance(stop, StopStatement)
    assert stop.stop_type is StopStatement.StopType.STOP_RUN


def test_leaf_and_arithmetic_statements_typed(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        "           ADD 1 TO WS-A.\n"
        "           CONTINUE.\n"
        "           GOBACK.\n"
    )
    # Act
    main = analyze(src).compilation_unit.program_unit.procedure_division.get_paragraph("MAIN")
    types = [s.statement_type for s in main.statements]
    # Assert
    assert StatementTypeEnum.ADD in types
    assert StatementTypeEnum.CONTINUE in types
    assert StatementTypeEnum.GO_BACK in types
