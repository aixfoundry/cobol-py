"""Phase C2: STRING / UNSTRING / INSPECT / SEARCH."""

from __future__ import annotations

from cobol_py.asg import (
    InspectStatement,
    SearchStatement,
    StatementTypeEnum,
    StringStatement,
    UnstringStatement,
)


_SRC = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. T.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-SRC PIC X(20).\n"
    "       01  WS-DST PIC X(20).\n"
    "       01  WS-D1  PIC X(5).\n"
    "       01  WS-D2  PIC X(5).\n"
    "       01  WS-TAB PIC 9 OCCURS 5.\n"
    "       PROCEDURE DIVISION.\n"
    "       P1.\n"
    "           STRING WS-SRC DELIMITED BY SIZE INTO WS-DST.\n"
    "           UNSTRING WS-SRC INTO WS-D1 WS-D2.\n"
    "           INSPECT WS-DST TALLYING WS-D1 FOR ALL 'A'.\n"
    "           SEARCH WS-TAB AT END CONTINUE WHEN WS-TAB (1) = 0 STOP RUN.\n"
)


def _stmts(analyze):
    return analyze(_SRC).compilation_unit.program_unit.procedure_division.get_paragraph("P1").statements


def test_string_into(analyze):
    s = next(x for x in _stmts(analyze) if isinstance(x, StringStatement))
    assert s.statement_type is StatementTypeEnum.STRING
    assert s.into_call is not None
    assert s.into_call.unwrap().name == "WS-DST"


def test_unstring_into(analyze):
    s = next(x for x in _stmts(analyze) if isinstance(x, UnstringStatement))
    assert {c.unwrap().name for c in s.into_calls} == {"WS-D1", "WS-D2"}


def test_inspect_data_item(analyze):
    s = next(x for x in _stmts(analyze) if isinstance(x, InspectStatement))
    assert s.data_item_call is not None
    assert s.data_item_call.unwrap().name == "WS-DST"


def test_search_data_call(analyze):
    s = next(x for x in _stmts(analyze) if isinstance(x, SearchStatement))
    assert s.data_call is not None
