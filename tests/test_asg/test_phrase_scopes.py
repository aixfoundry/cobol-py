"""Phrase scopes: AT END / INVALID KEY / ON SIZE ERROR / ON EXCEPTION / ON
OVERFLOW / AT END-OF-PAGE must own their nested statements (proleap parity).

Each test asserts two things: (1) the owning statement surfaces the phrase and
its nested statements, and (2) those nested statements do NOT leak into the
enclosing paragraph's flat statement list.
"""

from __future__ import annotations

from cobol_py.asg import (
    AddStatement,
    AtEndPhrase,
    CallStatement,
    DeleteStatement,
    InvalidKeyPhrase,
    MoveStatement,
    NotAtEndPhrase,
    NotInvalidKeyPhrase,
    NotOnExceptionClause,
    NotOnOverflowPhrase,
    NotOnSizeErrorPhrase,
    OnExceptionClause,
    OnOverflowPhrase,
    OnSizeErrorPhrase,
    ReadStatement,
    SearchStatement,
    StringStatement,
    WriteStatement,
)


def _statements(analyze, src):
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    return pd.root_paragraphs[0].statements


# Shared header: file-control + FD + working-storage the bodies reference.
_HEADER = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PHRASE.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IN-FILE ASSIGN TO 'IN'.
           SELECT OUT-FILE ASSIGN TO 'OUT'.
       DATA DIVISION.
       FILE SECTION.
       FD  IN-FILE.
       01  IN-REC PIC X(10).
       FD  OUT-FILE.
       01  OUT-REC PIC X(10).
       WORKING-STORAGE SECTION.
       01  WS-A PIC 9.
       01  WS-TBL OCCURS 5 PIC 9.
       PROCEDURE DIVISION.
       MAIN.
"""


# --- READ: INVALID KEY / NOT INVALID KEY / AT END / NOT AT END ---------------

def test_read_phrases_nest_and_do_not_leak(analyze):
    # Grammar order: invalidKey? notInvalidKey? atEnd? notAtEnd? END-READ?
    src = _HEADER + (
        "           READ IN-FILE RECORD\n"
        "               INVALID KEY MOVE 1 TO WS-A\n"
        "               NOT INVALID KEY MOVE 2 TO WS-A\n"
        "               AT END MOVE 3 TO WS-A\n"
        "               NOT AT END MOVE 4 TO WS-A\n"
        "           END-READ.\n"
        "           STOP RUN.\n"
    )
    stmts = _statements(analyze, src)
    # Only READ + STOP RUN at the paragraph level — the four nested MOVEs
    # belong to their phrases, not the paragraph.
    assert len(stmts) == 2
    read = stmts[0]
    assert isinstance(read, ReadStatement)
    assert isinstance(read.invalid_key_phrase, InvalidKeyPhrase)
    assert isinstance(read.not_invalid_key_phrase, NotInvalidKeyPhrase)
    assert isinstance(read.at_end_phrase, AtEndPhrase)
    assert isinstance(read.not_at_end_phrase, NotAtEndPhrase)
    assert [type(s).__name__ for s in read.invalid_key_phrase.statements] == ["MoveStatement"]
    assert [type(s).__name__ for s in read.not_invalid_key_phrase.statements] == ["MoveStatement"]
    assert [type(s).__name__ for s in read.at_end_phrase.statements] == ["MoveStatement"]
    assert [type(s).__name__ for s in read.not_at_end_phrase.statements] == ["MoveStatement"]
    # The MOVEs carried distinct receivers, so verify each phrase owns its own.
    assert read.invalid_key_phrase.statements[0] is not read.at_end_phrase.statements[0]


# --- DELETE: INVALID KEY / NOT INVALID KEY ---------------------------------

def test_delete_invalid_key_phrases_nest(analyze):
    src = _HEADER + (
        "           DELETE IN-FILE RECORD\n"
        "               INVALID KEY MOVE 1 TO WS-A\n"
        "               NOT INVALID KEY MOVE 2 TO WS-A\n"
        "           END-DELETE.\n"
        "           STOP RUN.\n"
    )
    stmts = _statements(analyze, src)
    assert len(stmts) == 2
    delete = stmts[0]
    assert isinstance(delete, DeleteStatement)
    assert isinstance(delete.invalid_key_phrase, InvalidKeyPhrase)
    assert isinstance(delete.not_invalid_key_phrase, NotInvalidKeyPhrase)
    assert len(delete.invalid_key_phrase.statements) == 1
    assert len(delete.not_invalid_key_phrase.statements) == 1


# --- WRITE: AT END-OF-PAGE / NOT AT END-OF-PAGE ----------------------------

def test_write_end_of_page_phrases_nest(analyze):
    src = _HEADER + (
        "           WRITE OUT-REC\n"
        "               AT END-OF-PAGE MOVE 1 TO WS-A\n"
        "               NOT AT END-OF-PAGE MOVE 2 TO WS-A\n"
        "           END-WRITE.\n"
        "           STOP RUN.\n"
    )
    stmts = _statements(analyze, src)
    assert len(stmts) == 2
    write = stmts[0]
    assert isinstance(write, WriteStatement)
    assert write.at_end_of_page_phrase is not None
    assert write.not_at_end_of_page_phrase is not None
    assert len(write.at_end_of_page_phrase.statements) == 1
    assert len(write.not_at_end_of_page_phrase.statements) == 1


# --- Arithmetic (ADD): ON SIZE ERROR / NOT ON SIZE ERROR -------------------

def test_add_size_error_phrases_nest(analyze):
    src = _HEADER + (
        "           ADD 1 TO WS-A\n"
        "               ON SIZE ERROR MOVE 1 TO WS-A\n"
        "               NOT ON SIZE ERROR MOVE 2 TO WS-A\n"
        "           END-ADD.\n"
        "           STOP RUN.\n"
    )
    stmts = _statements(analyze, src)
    assert len(stmts) == 2
    add = stmts[0]
    assert isinstance(add, AddStatement)
    assert isinstance(add.on_size_error_phrase, OnSizeErrorPhrase)
    assert isinstance(add.not_on_size_error_phrase, NotOnSizeErrorPhrase)
    assert len(add.on_size_error_phrase.statements) == 1
    assert len(add.not_on_size_error_phrase.statements) == 1


# --- CALL: ON EXCEPTION / NOT ON EXCEPTION / ON OVERFLOW -------------------

def test_call_exception_and_overflow_phrases_nest(analyze):
    src = _HEADER + (
        "           CALL 'SUB'\n"
        "               ON OVERFLOW MOVE 1 TO WS-A\n"
        "               ON EXCEPTION MOVE 2 TO WS-A\n"
        "               NOT ON EXCEPTION MOVE 3 TO WS-A\n"
        "           END-CALL.\n"
        "           STOP RUN.\n"
    )
    stmts = _statements(analyze, src)
    assert len(stmts) == 2
    call = stmts[0]
    assert isinstance(call, CallStatement)
    assert isinstance(call.on_overflow_phrase, OnOverflowPhrase)
    assert isinstance(call.on_exception_clause, OnExceptionClause)
    assert isinstance(call.not_on_exception_clause, NotOnExceptionClause)
    assert len(call.on_overflow_phrase.statements) == 1
    assert len(call.on_exception_clause.statements) == 1
    assert len(call.not_on_exception_clause.statements) == 1


# --- STRING: ON OVERFLOW / NOT ON OVERFLOW ---------------------------------

def test_string_overflow_phrases_nest(analyze):
    src = _HEADER + (
        "           STRING 'A' DELIMITED BY SIZE INTO WS-A\n"
        "               ON OVERFLOW MOVE 1 TO WS-A\n"
        "               NOT ON OVERFLOW MOVE 2 TO WS-A\n"
        "           END-STRING.\n"
        "           STOP RUN.\n"
    )
    stmts = _statements(analyze, src)
    assert len(stmts) == 2
    string = stmts[0]
    assert isinstance(string, StringStatement)
    assert isinstance(string.on_overflow_phrase, OnOverflowPhrase)
    assert isinstance(string.not_on_overflow_phrase, NotOnOverflowPhrase)
    assert len(string.on_overflow_phrase.statements) == 1
    assert len(string.not_on_overflow_phrase.statements) == 1


# --- SEARCH: AT END --------------------------------------------------------

def test_search_at_end_phrase_nests(analyze):
    src = _HEADER + (
        "           SEARCH WS-TBL\n"
        "               AT END MOVE 1 TO WS-A\n"
        "               WHEN WS-TBL(1) = 0\n"
        "                   MOVE 2 TO WS-A\n"
        "           END-SEARCH.\n"
        "           STOP RUN.\n"
    )
    stmts = _statements(analyze, src)
    search = stmts[0]
    assert isinstance(search, SearchStatement)
    assert isinstance(search.at_end_phrase, AtEndPhrase)
    assert [type(s).__name__ for s in search.at_end_phrase.statements] == ["MoveStatement"]


# --- DISPLAY: ON EXCEPTION (a non-file verb carrying exception clauses) -----

def test_display_exception_phrases_nest(analyze):
    src = _HEADER + (
        "           DISPLAY 'HI'\n"
        "               ON EXCEPTION MOVE 1 TO WS-A\n"
        "               NOT ON EXCEPTION MOVE 2 TO WS-A\n"
        "           END-DISPLAY.\n"
        "           STOP RUN.\n"
    )
    stmts = _statements(analyze, src)
    assert len(stmts) == 2
    from cobol_py.asg import DisplayStatement

    display = stmts[0]
    assert isinstance(display, DisplayStatement)
    assert isinstance(display.on_exception_clause, OnExceptionClause)
    assert isinstance(display.not_on_exception_clause, NotOnExceptionClause)
    assert len(display.on_exception_clause.statements) == 1
    assert len(display.not_on_exception_clause.statements) == 1


# --- SEARCH WHEN branches ---------------------------------------------------

def test_search_when_branches_nest(analyze):
    src = _HEADER + (
        "           SEARCH WS-TBL\n"
        "               AT END MOVE 1 TO WS-A\n"
        "               WHEN WS-TBL(1) = 1\n"
        "                   MOVE 2 TO WS-A\n"
        "               WHEN WS-TBL(1) = 2\n"
        "                   MOVE 3 TO WS-A\n"
        "           END-SEARCH.\n"
        "           STOP RUN.\n"
    )
    stmts = _statements(analyze, src)
    # SEARCH + STOP RUN only — the WHEN-branch + AT END MOVEs nest in their phrases.
    assert len(stmts) == 2
    search = stmts[0]
    assert isinstance(search, SearchStatement)
    from cobol_py.asg import SearchWhenPhrase

    assert len(search.when_phrases) == 2
    assert all(isinstance(p, SearchWhenPhrase) for p in search.when_phrases)
    # Each WHEN branch owns exactly one MOVE; conditions captured.
    assert [len(p.statements) for p in search.when_phrases] == [1, 1]
    assert all(p.condition is not None for p in search.when_phrases)


# --- EVALUATE WHEN / WHEN OTHER --------------------------------------------

def test_evaluate_when_and_when_other_nest(analyze):
    src = _HEADER + (
        "           EVALUATE WS-A\n"
        "               WHEN 1\n"
        "                   MOVE 2 TO WS-A\n"
        "               WHEN 2\n"
        "                   MOVE 3 TO WS-A\n"
        "               WHEN OTHER\n"
        "                   MOVE 4 TO WS-A\n"
        "           END-EVALUATE.\n"
        "           STOP RUN.\n"
    )
    stmts = _statements(analyze, src)
    # EVALUATE + STOP RUN only; branch MOVEs nest inside their phrases.
    assert len(stmts) == 2
    from cobol_py.asg import (
        EvaluateStatement,
        EvaluateWhenOther,
        EvaluateWhenPhrase,
    )

    evaluate = stmts[0]
    assert isinstance(evaluate, EvaluateStatement)
    assert len(evaluate.when_phrases) == 2
    assert all(isinstance(p, EvaluateWhenPhrase) for p in evaluate.when_phrases)
    assert [len(p.statements) for p in evaluate.when_phrases] == [1, 1]
    assert isinstance(evaluate.when_other, EvaluateWhenOther)
    assert len(evaluate.when_other.statements) == 1
    # when_count totals WHEN clauses across branches.
    assert evaluate.when_count == 2
