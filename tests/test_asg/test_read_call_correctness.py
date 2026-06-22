"""Correctness fixes for READ and CALL (parity with proleap).

READ: KEY operand, WITH (lock) phrase type, and NEXT-RECORD detection keyed on
the RECORD token (matching ``ScopeImpl.addReadStatement``). CALL: the GIVING /
RETURNING phrase operand.
"""

from __future__ import annotations

from cobol_py.asg import (
    LiteralValueStmt,
    ReadStatement,
)


_READ_SRC = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. T.\n"
    "       ENVIRONMENT DIVISION.\n"
    "       INPUT-OUTPUT SECTION.\n"
    "       FILE-CONTROL.\n"
    "           SELECT IN-FILE ASSIGN TO 'IN.DAT'.\n"
    "       DATA DIVISION.\n"
    "       FILE SECTION.\n"
    "       FD  IN-FILE.\n"
    "       01  IN-REC PIC X(10).\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-KEY PIC 9.\n"
    "       01  WS-REC PIC X(10).\n"
    "       PROCEDURE DIVISION.\n"
    "       MAIN.\n"
    "           READ IN-FILE WITH KEPT LOCK KEY IS WS-KEY\n"
    "              INVALID KEY CONTINUE\n"
    "           END-READ.\n"
    "           READ IN-FILE INTO WS-REC.\n"
    "           READ IN-FILE RECORD.\n"
)


def _read_stmts(analyze):
    return analyze(_READ_SRC).compilation_unit.program_unit.procedure_division.get_paragraph(
        "MAIN"
    ).statements


def test_read_key_operand(analyze):
    (read_key, _, _) = _read_stmts(analyze)
    assert read_key.key_call is not None
    assert read_key.key_call.name == "WS-KEY"


def test_read_with_kept_lock(analyze):
    (read_lock, _, _) = _read_stmts(analyze)
    assert read_lock.with_type is ReadStatement.WithType.KEPT_LOCK


def test_read_with_no_lock(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       INPUT-OUTPUT SECTION.\n"
        "       FILE-CONTROL.\n"
        "           SELECT IN-FILE ASSIGN TO 'IN.DAT'.\n"
        "       DATA DIVISION.\n"
        "       FILE SECTION.\n"
        "       FD  IN-FILE.\n"
        "       01  IN-REC PIC X(10).\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        "           READ IN-FILE WITH NO LOCK.\n"
    )
    read = analyze(src).compilation_unit.program_unit.procedure_division.get_paragraph("MAIN").statements[0]
    assert read.with_type is ReadStatement.WithType.NO_LOCK


def test_read_into_operand(analyze):
    (_, read_into, _) = _read_stmts(analyze)
    assert read_into.into_call is not None
    assert read_into.into_call.name == "WS-REC"


def test_read_next_record_keyed_on_record_token(analyze):
    (_, _, read_rec) = _read_stmts(analyze)
    # "READ IN-FILE RECORD" (no NEXT) -> next_record True, matching Java which
    # keys off ctx.RECORD() rather than ctx.NEXT().
    assert read_rec.next_record is True


def test_read_without_record_is_not_next(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       INPUT-OUTPUT SECTION.\n"
        "       FILE-CONTROL.\n"
        "           SELECT IN-FILE ASSIGN TO 'IN.DAT'.\n"
        "       DATA DIVISION.\n"
        "       FILE SECTION.\n"
        "       FD  IN-FILE.\n"
        "       01  IN-REC PIC X(10).\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        "           READ IN-FILE.\n"
    )
    read = analyze(src).compilation_unit.program_unit.procedure_division.get_paragraph("MAIN").statements[0]
    assert read.next_record is False


# --- CALL GIVING -----------------------------------------------------------

_CALL_SRC = (
    "       IDENTIFICATION DIVISION.\n"
    '       PROGRAM-ID. T.\n'
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-A PIC 9.\n"
    "       01  WS-RC PIC 9.\n"
    "       PROCEDURE DIVISION.\n"
    "       MAIN.\n"
    '           CALL "SUB" USING WS-A GIVING WS-RC.\n'
)


def test_call_giving_phrase(analyze):
    call = analyze(_CALL_SRC).compilation_unit.program_unit.procedure_division.get_paragraph(
        "MAIN"
    ).statements[0]
    assert call.giving_call is not None
    assert call.giving_call.name == "WS-RC"


def test_call_literal_program_name(analyze):
    call = analyze(_CALL_SRC).compilation_unit.program_unit.procedure_division.get_paragraph(
        "MAIN"
    ).statements[0]
    # CALL "SUB" -> program name is a literal value stmt
    assert isinstance(call.program_value_stmt, LiteralValueStmt)
