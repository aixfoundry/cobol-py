"""Phase C2: CALL / SET / EVALUATE / INITIALIZE + Wave 5 decomposed stub verbs."""

from __future__ import annotations

from cobol_py.asg import (
    CallStatement,
    DisableStatement,
    DisableType,
    EnableStatement,
    EnableType,
    EntryStatement,
    EvaluateStatement,
    ExecCicsStatement,
    ExecSqlStatement,
    ExhibitStatement,
    GenerateStatement,
    InitializeStatement,
    InitiateStatement,
    PurgeStatement,
    ReceiveStatement,
    ReceiveType,
    SendStatement,
    SendType,
    SetStatement,
    StatementTypeEnum,
    TerminateStatement,
    UseStatement,
    UseType,
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


# === Wave 5: decomposed stub verb tests =====================================

def _single(analyze, line, data="       01  WS-A PIC 9.\n", pd_para="P1"):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        + data
        + "       PROCEDURE DIVISION.\n"
        f"       {pd_para}.\n"
        f"           {line}\n"
        f"           STOP RUN.\n"
    )
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    return pd.get_paragraph(pd_para).statements[0] if pd else None


# -- EXEC verbs --------------------------------------------------------------

def test_exec_cics_extracts_text(analyze):
    stmt = _single(analyze, "EXEC CICS SEND TEXT FROM(WS-A) END-EXEC.")
    assert isinstance(stmt, ExecCicsStatement)
    assert "SEND TEXT FROM" in stmt.exec_cics_text.upper()
    assert "EXECCICS" not in stmt.exec_cics_text
    assert "}" not in stmt.exec_cics_text


def test_exec_sql_extracts_text(analyze):
    stmt = _single(analyze, "EXEC SQL SELECT A INTO :B END-EXEC.")
    assert isinstance(stmt, ExecSqlStatement)
    assert "SELECT" in stmt.exec_sql_text.upper()
    assert "EXECSQL" not in stmt.exec_sql_text


# -- DISABLE / ENABLE --------------------------------------------------------

def test_disable_input(analyze):
    stmt = _single(analyze, "DISABLE INPUT CD1 KEY WS-A.")
    assert isinstance(stmt, DisableStatement)
    assert stmt.disable_type is DisableType.INPUT
    assert stmt.communication_description_call is not None
    assert stmt.key_value_stmt is not None

def test_disable_output_terminal(analyze):
    # Grammar: OUTPUT (no TERMINAL option). Use I-O for TERMINAL.
    stmt = _single(analyze, "DISABLE I-O TERMINAL CD1 KEY 'X'.")
    assert stmt.disable_type is DisableType.INPUT_OUTPUT
    assert stmt.terminal is True

def test_enable_input(analyze):
    stmt = _single(analyze, "ENABLE INPUT CD1 KEY WS-A.")
    assert isinstance(stmt, EnableStatement)
    assert stmt.enable_type is EnableType.INPUT
    assert stmt.communication_description_call is not None

def test_enable_io_terminal(analyze):
    stmt = _single(analyze, "ENABLE I-O TERMINAL CD1 KEY WS-A.")
    assert isinstance(stmt, EnableStatement)
    # ENABLE I-O should parse as EnableType.INPUT_OUTPUT
    assert stmt.enable_type is EnableType.INPUT_OUTPUT
    assert stmt.terminal is True


# -- ENTRY -------------------------------------------------------------------

def test_entry_literal(analyze):
    stmt = _single(analyze, "ENTRY 'SUB-ENTRY'.")
    assert isinstance(stmt, EntryStatement)
    assert stmt.entry_value_stmt is not None

def test_entry_with_using(analyze):
    stmt = _single(analyze, "ENTRY 'SUB' USING WS-A.",
                   data="       01  WS-A PIC 9.\n       01  WS-B PIC 9.\n")
    assert isinstance(stmt, EntryStatement)
    assert len(stmt.using_calls) == 1


# -- EXHIBIT -----------------------------------------------------------------

def test_exhibit_operands(analyze):
    stmt = _single(analyze, "EXHIBIT WS-A.")
    assert isinstance(stmt, ExhibitStatement)
    assert len(stmt.operands) == 1

def test_exhibit_named_changed(analyze):
    stmt = _single(analyze, "EXHIBIT NAMED CHANGED WS-A.")
    assert isinstance(stmt, ExhibitStatement)
    assert stmt.named is True
    assert stmt.changed is True


# -- GENERATE / INITIATE / TERMINATE / PURGE ---------------------------------

def test_generate_report(analyze):
    stmt = _single(analyze, "GENERATE RPT-A.")
    assert isinstance(stmt, GenerateStatement)
    assert stmt.report_description_call is not None

def test_initiate_reports(analyze):
    stmt = _single(analyze, "INITIATE RPT-A RPT-B.")
    assert isinstance(stmt, InitiateStatement)
    assert len(stmt.report_calls) == 2

def test_terminate_report(analyze):
    stmt = _single(analyze, "TERMINATE RPT-A.")
    assert isinstance(stmt, TerminateStatement)
    assert stmt.report_call is not None

def test_purge_cd_names(analyze):
    stmt = _single(analyze, "PURGE CD-A CD-B.")
    assert isinstance(stmt, PurgeStatement)
    assert len(stmt.communication_description_entry_calls) == 2


# -- RECEIVE -----------------------------------------------------------------

def test_receive_from(analyze):
    stmt = _single(analyze, "RECEIVE WS-MSG FROM THREAD WS-THR.")
    assert isinstance(stmt, ReceiveStatement)
    assert stmt.receive_type is ReceiveType.FROM
    assert stmt.receive_from_statement is not None
    # data_call
    assert stmt.receive_from_statement.data_call is not None
    # from_
    rf = stmt.receive_from_statement.from_
    assert rf is not None
    assert rf.from_type == rf.FromType.THREAD

def test_receive_into(analyze):
    stmt = _single(analyze, "RECEIVE CD-A MESSAGE INTO WS-A.",
                   data="       01  WS-A PIC 9.\n")
    assert isinstance(stmt, ReceiveStatement)
    assert stmt.receive_type is ReceiveType.INTO
    assert stmt.receive_into_statement is not None
    assert stmt.receive_into_statement.communication_description_call is not None
    assert stmt.receive_into_statement.into_call is not None


# -- SEND --------------------------------------------------------------------

def test_send_sync(analyze):
    stmt = _single(analyze, "SEND WS-A.")
    assert isinstance(stmt, SendStatement)
    assert stmt.send_type is SendType.SYNC
    assert stmt.sync is not None
    assert stmt.sync.receiving_program_value_stmt is not None


# -- USE ---------------------------------------------------------------------
# USE is only valid inside DECLARATIVES (currently stubbed). Model classes are
# verified for import correctness; full parse tests need DECLARATIVES support.

def test_use_model_imports():
    """Verify the USE sub-model classes import cleanly."""
    from cobol_py.asg import (
        UseAfterOn,
        UseAfterStatement,
        UseDebugOn,
        UseDebugStatement,
        UseStatement,
        UseType,
    )
    assert UseType.AFTER is not None
    assert UseType.DEBUG is not None
    assert UseAfterOn.AfterOnType.FILE is not None
