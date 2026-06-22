"""C2 tail: SORT/MERGE/ALTER/CANCEL/RETURN/RELEASE, IF Then/Else, PERFORM inline."""

from __future__ import annotations

from cobol_py.asg import (
    AlterStatement,
    CancelStatement,
    MergeStatement,
    MoveStatement,
    PerformStatement,
    ProceedTo,
    ReleaseStatement,
    ReturnStatement,
    SortStatement,
    StatementTypeEnum,
)


def _statements(analyze, src):
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    # Statements live on the root paragraph (MAIN) for these single-para fixtures.
    return pd.root_paragraphs[0].statements


# Shared header: a file-control + working-storage environment that the file / data
# references below resolve against.
_HEADER = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TESTC2.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT SORT-FILE ASSIGN TO 'SF'.
           SELECT IN-FILE ASSIGN TO 'IN'.
           SELECT OUT-FILE ASSIGN TO 'OUT'.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 SORT-KEY PIC 9(4).
       01 OUT-REC PIC X(10).
       PROCEDURE DIVISION.
       MAIN.
"""


# --- SORT ------------------------------------------------------------------

def test_sort_resolves_file_key_using_giving(analyze):
    src = _HEADER + (
        "           SORT SORT-FILE ON ASCENDING KEY SORT-KEY\n"
        "                USING IN-FILE\n"
        "                GIVING OUT-FILE.\n"
        "           STOP RUN.\n"
    )
    stmts = _statements(analyze, src)
    sort = stmts[0]
    assert isinstance(sort, SortStatement)
    assert sort.statement_type is StatementTypeEnum.SORT
    # Sort file + USING/GIVING files resolve to their SELECT entries.
    assert sort.file_call is not None
    assert [c.unwrap().name for c in sort.using_calls] == ["IN-FILE"]
    assert [c.unwrap().name for c in sort.giving_calls] == ["OUT-FILE"]
    # ON KEY data item resolves to its working-storage entry.
    assert [c.unwrap().name for c in sort.key_calls] == ["SORT-KEY"]


def test_sort_input_output_procedure(analyze):
    src = (
        _HEADER
        + "           SORT SORT-FILE ON DESCENDING KEY SORT-KEY\n"
        + "                INPUT PROCEDURE IN-PARA\n"
        + "                OUTPUT PROCEDURE OUT-PARA THROUGH OUT-PARA-2.\n"
        + "           STOP RUN.\n"
    )
    sort = _statements(analyze, src)[0]
    assert isinstance(sort, SortStatement)
    # Input/output procedure names capture both endpoints of a THROUGH range.
    assert [c.name for c in sort.input_procedure_calls] == ["IN-PARA"]
    assert [c.name for c in sort.output_procedure_calls] == ["OUT-PARA", "OUT-PARA-2"]


# --- MERGE -----------------------------------------------------------------

def test_merge_resolves_keys_and_files(analyze):
    src = _HEADER + (
        "           MERGE SORT-FILE ON DESCENDING KEY SORT-KEY\n"
        "                USING IN-FILE\n"
        "                GIVING OUT-FILE.\n"
        "           STOP RUN.\n"
    )
    merge = _statements(analyze, src)[0]
    assert isinstance(merge, MergeStatement)
    assert merge.statement_type is StatementTypeEnum.MERGE
    assert [c.unwrap().name for c in merge.key_calls] == ["SORT-KEY"]
    assert [c.unwrap().name for c in merge.using_calls] == ["IN-FILE"]
    assert [c.unwrap().name for c in merge.giving_calls] == ["OUT-FILE"]


# --- ALTER -----------------------------------------------------------------

def test_alter_captures_proceed_to(analyze):
    src = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ALT.
       PROCEDURE DIVISION.
       PARA-A.
           GO TO PARA-B.
       PARA-B.
           STOP RUN.
       PARA-C.
           ALTER PARA-A TO PROCEED TO PARA-C.
"""
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    by_name = {p.name: p for p in pd.paragraphs}
    alter = by_name["PARA-C"].statements[0]
    assert isinstance(alter, AlterStatement)
    assert len(alter.proceed_tos) == 1
    proceed_to = alter.proceed_tos[0]
    assert isinstance(proceed_to, ProceedTo)
    # Source/target resolve to the named paragraphs.
    assert proceed_to.source_call.name == "PARA-A"
    assert proceed_to.target_call.name == "PARA-C"


# --- IF Then/Else containers ----------------------------------------------

def test_if_then_else_containers_group_statements(analyze):
    src = _HEADER + (
        "           IF SORT-KEY > 0\n"
        "               MOVE 1 TO SORT-KEY\n"
        "           ELSE\n"
        "               MOVE 2 TO SORT-KEY\n"
        "           END-IF.\n"
        "           STOP RUN.\n"
    )
    if_stmt = _statements(analyze, src)[0]
    # The IF still attaches flat to the paragraph, but Then/Else surface the
    # nested statements grouped by branch.
    assert if_stmt.then is not None
    assert if_stmt.else_ is not None
    then_stmts = if_stmt.then.statements
    else_stmts = if_stmt.else_.statements
    assert len(then_stmts) == 1 and isinstance(then_stmts[0], MoveStatement)
    assert len(else_stmts) == 1 and isinstance(else_stmts[0], MoveStatement)


# --- PERFORM inline body ---------------------------------------------------

def test_perform_inline_body_groups_statements(analyze):
    src = _HEADER + (
        "           PERFORM 3 TIMES\n"
        "               MOVE 1 TO SORT-KEY\n"
        "           END-PERFORM.\n"
        "           STOP RUN.\n"
    )
    perform = _statements(analyze, src)[0]
    assert isinstance(perform, PerformStatement)
    assert perform.perform_inline_statement is not None
    body = perform.perform_inline_statement.statements
    assert len(body) == 1 and isinstance(body[0], MoveStatement)


# --- CANCEL / RETURN / RELEASE --------------------------------------------

def test_cancel_literal(analyze):
    src = _HEADER + "           CANCEL 'SUBPROG'.\n           STOP RUN.\n"
    cancel = _statements(analyze, src)[0]
    assert isinstance(cancel, CancelStatement)
    assert len(cancel.value_stmts) == 1


def test_return_and_release(analyze):
    src = (
        _HEADER
        + "           RETURN SORT-FILE RECORD INTO SORT-KEY\n"
        + "              AT END CONTINUE END-RETURN.\n"
        + "           RELEASE OUT-REC FROM SORT-KEY.\n"
        + "           STOP RUN.\n"
    )
    stmts = _statements(analyze, src)
    ret = stmts[0]
    assert isinstance(ret, ReturnStatement)
    assert ret.file_call is not None
    assert ret.into_call is not None and ret.into_call.unwrap().name == "SORT-KEY"
    rel = stmts[1]
    assert isinstance(rel, ReleaseStatement)
    assert rel.record_call.unwrap().name == "OUT-REC"
    assert rel.from_call is not None and rel.from_call.unwrap().name == "SORT-KEY"
