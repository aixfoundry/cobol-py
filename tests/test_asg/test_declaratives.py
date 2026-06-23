"""DECLARATIVES block: Declaratives -> Declarative -> SectionHeader + UseStatement.

Ports ``metamodel/procedure/declaratives/{Declaratives,Declarative,
SectionHeader}``. The block is the only construct where a USE statement may
appear; the declarative owns the USE rather than the procedure division.
"""

from __future__ import annotations

from cobol_py.asg import (
    DebugOnType,
    Declarative,
    Declaratives,
    SectionHeader,
    UseAfterOn,
    UseStatement,
    UseType,
)


_AFTER_SRC = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. T.\n"
    "       DATA DIVISION.\n"
    "       FILE SECTION.\n"
    "       FD  IN-FILE.\n"
    "       01  IN-REC PIC X.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-A PIC 9.\n"
    "       PROCEDURE DIVISION.\n"
    "       DECLARATIVES.\n"
    "       ERR-SEC SECTION.\n"
    "           USE AFTER STANDARD ERROR PROCEDURE ON IN-FILE.\n"
    "       ERR-PARA.\n"
    "           MOVE 1 TO WS-A.\n"
    "       END DECLARATIVES.\n"
    "       MAIN-PARA.\n"
    "           MOVE 0 TO WS-A.\n"
    "           STOP RUN.\n"
)


_DEBUG_SRC = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. T.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-A PIC 9.\n"
    "       01  WS-B PIC 9.\n"
    "       PROCEDURE DIVISION.\n"
    "       DECLARATIVES.\n"
    "       DBG-SEC SECTION.\n"
    "           USE FOR DEBUGGING ON ALL PROCEDURES.\n"
    "       DBG-PARA.\n"
    "           MOVE 1 TO WS-A.\n"
    "       END DECLARATIVES.\n"
    "       MAIN-PARA.\n"
    "           MOVE 0 TO WS-B.\n"
    "           STOP RUN.\n"
)


def _pd(analyze, src):
    return analyze(src).compilation_unit.program_unit.procedure_division


# -- USE AFTER ----------------------------------------------------------------


def test_declaratives_after_builds_typed_tree(analyze):
    pd = _pd(analyze, _AFTER_SRC)
    assert isinstance(pd.declaratives, Declaratives)
    assert len(pd.declaratives.declaratives) == 1

    declarative = pd.declaratives.declaratives[0]
    assert isinstance(declarative, Declarative)
    assert isinstance(declarative.section_header, SectionHeader)


def test_declarative_owns_use_after_statement(analyze):
    declarative = _pd(analyze, _AFTER_SRC).declaratives.declaratives[0]
    use = declarative.use_statement

    assert isinstance(use, UseStatement)
    assert use.use_type is UseType.AFTER
    assert use.use_after_statement is not None
    assert use.use_after_statement.after_on is not None
    # ON IN-FILE resolves to a file-name reference.
    assert use.use_after_statement.after_on.after_on_type is UseAfterOn.AfterOnType.FILE
    assert use.use_after_statement.after_on.file_calls


def test_use_statement_is_not_a_top_level_statement(analyze):
    """The declarative's USE must not leak into procedure_division.statements."""
    pd = _pd(analyze, _AFTER_SRC)
    assert not any(isinstance(s, UseStatement) for s in pd.statements)


def test_declarative_body_paragraph_is_registered(analyze):
    """The paragraph inside the declarative attaches to the procedure division,
    mirroring proleap (Declaratives/Declarative are not scopes)."""
    pd = _pd(analyze, _AFTER_SRC)
    assert pd.get_paragraph("ERR-PARA") is not None
    assert pd.get_paragraph("MAIN-PARA") is not None


# -- USE FOR DEBUGGING --------------------------------------------------------


def test_declaratives_debug_builds_typed_tree(analyze):
    pd = _pd(analyze, _DEBUG_SRC)
    assert isinstance(pd.declaratives, Declaratives)
    declarative = pd.declaratives.declaratives[0]
    assert isinstance(declarative.section_header, SectionHeader)

    use = declarative.use_statement
    assert use.use_type is UseType.DEBUG
    assert use.use_debug_statement is not None
    assert len(use.use_debug_statement.debug_ons) == 1
    assert use.use_debug_statement.debug_ons[0].debug_on_type is DebugOnType.ALL_PROCEDURES


def test_declaratives_debug_use_not_top_level(analyze):
    pd = _pd(analyze, _DEBUG_SRC)
    assert not any(isinstance(s, UseStatement) for s in pd.statements)


# -- absence ------------------------------------------------------------------


def test_no_declaratives_is_none(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           MOVE 0 TO WS-A.\n"
        "           STOP RUN.\n"
    )
    assert _pd(analyze, src).declaratives is None
