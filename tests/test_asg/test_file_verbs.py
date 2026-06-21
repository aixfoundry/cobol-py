"""Phase C2: file I/O verbs resolve file-name references."""

from __future__ import annotations

from cobol_py.asg import (
    CallTypeEnum,
    OpenStatement,
    ReadStatement,
    WriteStatement,
    CloseStatement,
    StatementTypeEnum,
)


_SRC = (
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
    "       PROCEDURE DIVISION.\n"
    "       P1.\n"
    "           OPEN INPUT IN-FILE OUTPUT OUT-FILE.\n"
    "           READ IN-FILE NEXT RECORD.\n"
    "           WRITE OUT-REC.\n"
    "           CLOSE IN-FILE OUT-FILE.\n"
)


def _stmts(analyze):
    return analyze(_SRC).compilation_unit.program_unit.procedure_division.get_paragraph("P1").statements


def test_open_resolves_file_calls(analyze):
    stmts = _stmts(analyze)
    open_stmt = next(s for s in stmts if isinstance(s, OpenStatement))
    targets = [c.unwrap() for c in open_stmt.file_calls]
    assert {t.name for t in targets} == {"IN-FILE", "OUT-FILE"}
    assert all(t.call_type is CallTypeEnum.FILE_CONTROL_ENTRY_CALL for t in targets)


def test_read_file_and_next_record(analyze):
    stmts = _stmts(analyze)
    read = next(s for s in stmts if isinstance(s, ReadStatement))
    assert read.file_call.unwrap().name == "IN-FILE"
    assert read.file_call.unwrap().call_type is CallTypeEnum.FILE_CONTROL_ENTRY_CALL
    assert read.next_record is True


def test_write_record_call(analyze):
    stmts = _stmts(analyze)
    write = next(s for s in stmts if isinstance(s, WriteStatement))
    assert write.record_call.unwrap().name == "OUT-REC"


def test_close_resolves_file_calls(analyze):
    stmts = _stmts(analyze)
    close = next(s for s in stmts if isinstance(s, CloseStatement))
    assert {c.unwrap().name for c in close.file_calls} == {"IN-FILE", "OUT-FILE"}


def test_file_control_backlinks(analyze):
    # OPEN + READ + CLOSE all reference IN-FILE -> back-links on the SELECT.
    program = analyze(_SRC)
    fce = (
        program.compilation_unit.program_unit.environment_division.input_output_section.file_control_paragraph.get_file_control_entry("IN-FILE")
    )
    assert len(fce.calls) >= 3
