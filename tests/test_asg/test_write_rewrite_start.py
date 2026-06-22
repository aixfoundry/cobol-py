"""Correctness fixes for WRITE / REWRITE / START (parity with proleap).

WRITE: FROM becomes a ValueStmt (so ``WRITE r FROM <literal>`` keeps the
literal) + the advancing phrase (BEFORE/AFTER + PAGE/LINES/MNEMONIC).
REWRITE: the FROM operand. START: KEY type + comparison call.
"""

from __future__ import annotations

from cobol_py.asg import (
    CallValueStmt,
    LiteralValueStmt,
    RewriteStatement,
    StartStatement,
    WriteStatement,
)


def _main(analyze, body):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       INPUT-OUTPUT SECTION.\n"
        "       FILE-CONTROL.\n"
        "           SELECT IN-FILE ASSIGN TO 'IN.DAT'.\n"
        "           SELECT OUT-FILE ASSIGN TO 'OUT.DAT'.\n"
        "       DATA DIVISION.\n"
        "       FILE SECTION.\n"
        "       FD  IN-FILE.\n"
        "       01  IN-REC PIC X(10).\n"
        "       FD  OUT-FILE.\n"
        "       01  OUT-REC PIC X(10).\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-SRC PIC X(10).\n"
        "       01  WS-KEY PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n" + body
    )
    return analyze(src).compilation_unit.program_unit.procedure_division.get_paragraph("MAIN").statements


# --- WRITE -----------------------------------------------------------------

def test_write_from_identifier(analyze):
    (write,) = _main(analyze, "           WRITE OUT-REC FROM WS-SRC.\n")
    assert isinstance(write, WriteStatement)
    assert write.from_value_stmt is not None
    assert isinstance(write.from_value_stmt, CallValueStmt)
    assert write.from_value_stmt.call.name == "WS-SRC"


def test_write_from_literal(analyze):
    (write,) = _main(analyze, '           WRITE OUT-REC FROM "LIT".\n')
    # FROM <literal> must be retained as a literal value stmt (was dropped when
    # FROM was modelled as a bare Call).
    assert isinstance(write.from_value_stmt, LiteralValueStmt)


def test_write_advancing_lines(analyze):
    (write,) = _main(analyze, "           WRITE OUT-REC AFTER ADVANCING 2 LINES.\n")
    assert write.advancing_position is WriteStatement.PositionType.AFTER
    assert write.advancing_type is WriteStatement.AdvancingType.LINES
    assert isinstance(write.advancing_lines_value_stmt, LiteralValueStmt)


def test_write_advancing_page_before(analyze):
    (write,) = _main(analyze, "           WRITE OUT-REC BEFORE ADVANCING PAGE.\n")
    assert write.advancing_position is WriteStatement.PositionType.BEFORE
    assert write.advancing_type is WriteStatement.AdvancingType.PAGE


# --- REWRITE ---------------------------------------------------------------

def test_rewrite_from_operand(analyze):
    (rewrite,) = _main(analyze, "           REWRITE IN-REC FROM WS-SRC.\n")
    assert isinstance(rewrite, RewriteStatement)
    assert rewrite.from_call is not None
    assert rewrite.from_call.name == "WS-SRC"


# --- START -----------------------------------------------------------------

def test_start_key_greater(analyze):
    (start,) = _main(analyze, "           START IN-FILE KEY IS GREATER THAN WS-KEY.\n")
    assert isinstance(start, StartStatement)
    assert start.key_type is StartStatement.KeyType.GREATER
    assert start.key_comparison_call.name == "WS-KEY"


def test_start_key_equal(analyze):
    (start,) = _main(analyze, "           START IN-FILE KEY IS EQUAL TO WS-KEY.\n")
    assert start.key_type is StartStatement.KeyType.EQUAL
    assert start.key_comparison_call.name == "WS-KEY"
