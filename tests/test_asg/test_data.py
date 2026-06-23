"""Phase D: data division — hierarchy, reference resolution, and clause decomposition."""

from __future__ import annotations

from cobol_py.asg import (
    CallTypeEnum,
    DataDescriptionEntryCall,
    DataDescriptionEntryCondition,
    DataDescriptionEntryGroup,
    DataDescriptionEntryRename,
    OccursSortOrder,
    PictureClause,
    SignClauseType,
    UsageClauseType,
    ValueClause,
    ValueInterval,
)


def test_working_storage_entries_built(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       01  WS-B PIC X(3).\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    # Act
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    # Assert
    assert {e.name for e in ws.root_data_description_entries} == {"WS-A", "WS-B"}
    a = ws.get_data_description_entry("WS-A")
    assert a.level_number == 1
    assert a.picture_clause is not None  # PIC clause captured
    assert a.picture_clause.picture_string == "9"


def test_group_hierarchy_resolved_by_level(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-REC.\n"
        "           05 WS-A PIC 9.\n"
        "           05 WS-B PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    # Act
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    rec = ws.get_data_description_entry("WS-REC")
    # Assert
    assert isinstance(rec, DataDescriptionEntryGroup)
    assert [c.name for c in rec.data_description_entries] == ["WS-A", "WS-B"]
    assert all(c.parent_data_description_entry_group is rec for c in rec.data_description_entries)


def test_move_resolves_to_data_description_entry(analyze):
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
    pu = analyze(src).compilation_unit.program_unit
    move = pu.procedure_division.get_paragraph("MAIN").statements[0]
    targets = [c.unwrap() for c in move.move_to.receiving_area_calls]
    # Assert: both receiving areas resolve to real data-description entries.
    assert all(isinstance(t, DataDescriptionEntryCall) for t in targets)
    assert [t.name for t in targets] == ["WS-A", "WS-B"]
    assert move.move_to.receiving_area_calls[0].unwrap().data_description_entry.name == "WS-A"


def test_call_backlinks_registered_on_declaration(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        "           MOVE 1 TO WS-A.\n"
        "           MOVE 2 TO WS-A.\n"
    )
    # Act
    ws_a = analyze(src).compilation_unit.program_unit.data_division.working_storage_section.get_data_description_entry("WS-A")
    # Assert: each reference registered a back-link on the declaration.
    assert len(ws_a.calls) == 2


def test_unknown_reference_is_undefined(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        "           MOVE 1 TO NO-SUCH-NAME.\n"
    )
    # Act
    move = analyze(src).compilation_unit.program_unit.procedure_division.get_paragraph("MAIN").statements[0]
    target = move.move_to.receiving_area_calls[0].unwrap()
    # Assert
    assert target.call_type is CallTypeEnum.UNDEFINED_CALL


# === Phase D2: clause decomposition tests ===================================

def test_picture_clause_captured(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-X PIC X(10).\n"
        "       01  WS-9 PIC 9(5)V99.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    x = ws.get_data_description_entry("WS-X")
    assert x.picture_clause is not None
    assert isinstance(x.picture_clause, PictureClause)
    assert x.picture_clause.picture_string == "X(10)"
    n9 = ws.get_data_description_entry("WS-9")
    assert n9.picture_clause.picture_string == "9(5)V99"


def test_value_clause_single_interval(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-FLAG PIC 9 VALUE 0.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    entry = ws.get_data_description_entry("WS-FLAG")
    assert entry.value_clause is not None
    assert isinstance(entry.value_clause, ValueClause)
    assert len(entry.value_clause.value_intervals) == 1
    iv = entry.value_clause.value_intervals[0]
    assert isinstance(iv, ValueInterval)
    assert iv.to_value_stmt is None  # single value, no THROUGH


def test_value_clause_multi_interval(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-CODE PIC 9 VALUE 1, 2, 3.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    entry = ws.get_data_description_entry("WS-CODE")
    assert entry.value_clause is not None
    assert len(entry.value_clause.value_intervals) == 3


def test_value_clause_through_range(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-RANGE PIC 9 VALUE 1 THROUGH 10.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    entry = ws.get_data_description_entry("WS-RANGE")
    iv = entry.value_clause.value_intervals[0]
    assert iv.to_value_stmt is not None
    assert iv.through is True


def test_condition_88_has_value_clause(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-STATUS PIC 9.\n"
        "           88 WS-OK VALUE 0.\n"
        "           88 WS-ERR VALUES 1 THRU 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    ok = ws.get_data_description_entry("WS-OK")
    assert isinstance(ok, DataDescriptionEntryCondition)
    assert ok.level_number == 88
    assert ok.value_clause is not None
    assert len(ok.value_clause.value_intervals) == 1
    err = ws.get_data_description_entry("WS-ERR")
    assert err.value_clause is not None
    assert len(err.value_clause.value_intervals) == 1
    assert err.value_clause.value_intervals[0].through is True


def test_rename_66_has_renames_clause(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-REC.\n"
        "           05 WS-A PIC X.\n"
        "           05 WS-B PIC X.\n"
        "       66  WS-AB RENAMES WS-A THRU WS-B.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    ab = ws.get_data_description_entry("WS-AB")
    assert isinstance(ab, DataDescriptionEntryRename)
    assert ab.level_number == 66
    assert ab.renames_clause is not None
    assert len(ab.renames_clause.calls) == 2  # from + to


def test_usage_clause_comp_3(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-AMT PIC 9(5) USAGE COMP-3.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    entry = ws.get_data_description_entry("WS-AMT")
    assert entry.usage_clause is not None
    assert entry.usage_clause.usage_clause_type is UsageClauseType.COMP_3


def test_usage_clause_index_pointer(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-IDX USAGE INDEX.\n"
        "       01  WS-PTR USAGE POINTER.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    assert ws.get_data_description_entry("WS-IDX").usage_clause.usage_clause_type is UsageClauseType.INDEX
    assert ws.get_data_description_entry("WS-PTR").usage_clause.usage_clause_type is UsageClauseType.POINTER


def test_redefines_clause(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-REC.\n"
        "           05 WS-OLD PIC X(10).\n"
        "           05 WS-NEW REDEFINES WS-OLD PIC 9(10).\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    rec = ws.get_data_description_entry("WS-REC")
    new_entry = rec.data_description_entries[1]
    assert new_entry.name == "WS-NEW"
    assert new_entry.redefines_clause is not None


def test_sign_clause_leading_separate(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-SIGNED PIC S9(5) SIGN IS LEADING SEPARATE.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    entry = ws.get_data_description_entry("WS-SIGNED")
    assert entry.sign_clause is not None
    assert entry.sign_clause.sign_clause_type is SignClauseType.LEADING
    assert entry.sign_clause.separate is True


def test_sign_clause_trailing(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-SIGNED PIC S9(5) SIGN TRAILING.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    entry = ws.get_data_description_entry("WS-SIGNED")
    assert entry.sign_clause.sign_clause_type is SignClauseType.TRAILING
    assert entry.sign_clause.separate is False


def test_occurs_clause_simple(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-TABLE.\n"
        "           05 WS-ELEM OCCURS 10 PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    rec = ws.get_data_description_entry("WS-TABLE")
    elem = rec.data_description_entries[0]
    assert elem.name == "WS-ELEM"
    assert len(elem.occurs_clauses) == 1


def test_occurs_with_sort_keys(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-TABLE.\n"
        "           05 WS-ELEM OCCURS 10\n"
        "               ASCENDING KEY WS-KEY\n"
        "               DESCENDING WS-DESC PIC 9.\n"
        "           05 WS-KEY PIC X.\n"
        "           05 WS-DESC PIC X.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    rec = ws.get_data_description_entry("WS-TABLE")
    elem = rec.data_description_entries[0]
    assert len(elem.occurs_clauses[0].occurs_sorts) >= 2


def test_occurs_indexed_by(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-TABLE.\n"
        "           05 WS-ELEM OCCURS 10 INDEXED BY WS-IDX PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    rec = ws.get_data_description_entry("WS-TABLE")
    elem = rec.data_description_entries[0]
    occurs = elem.occurs_clauses[0]
    assert occurs.occurs_indexed is not None
    assert len(occurs.occurs_indexed.indices) == 1
    assert occurs.occurs_indexed.indices[0].name == "WS-IDX"


def test_occurs_depending_on(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-COUNT PIC 9.\n"
        "       01  WS-TABLE.\n"
        "           05 WS-ELEM OCCURS 1 TO 100 TIMES\n"
        "               DEPENDING ON WS-COUNT PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    rec = ws.get_data_description_entry("WS-TABLE")
    elem = rec.data_description_entries[0]
    occurs = elem.occurs_clauses[0]
    assert occurs.occurs_depending is not None


def test_justified_clause(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-J PIC X(10) JUSTIFIED RIGHT.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    entry = ws.get_data_description_entry("WS-J")
    assert entry.justified_clause is not None


def test_blank_when_zero_clause(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-BZ PIC 9(5) BLANK WHEN ZERO.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    entry = ws.get_data_description_entry("WS-BZ")
    assert entry.blank_when_zero_clause is not None
    assert entry.blank_when_zero_clause.blank_when_zero is True


def test_synchronized_clause(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-SYNC PIC X SYNCHRONIZED LEFT.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    entry = ws.get_data_description_entry("WS-SYNC")
    assert entry.synchronized_clause is not None


def test_external_clause(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-EXT PIC X IS EXTERNAL.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    entry = ws.get_data_description_entry("WS-EXT")
    assert entry.external_clause is not None
    assert entry.external_clause.external is True


def test_global_clause(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-GLB PIC X IS GLOBAL.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    entry = ws.get_data_description_entry("WS-GLB")
    assert entry.global_clause is not None
    assert entry.global_clause.global_ is True


def test_filler_entry(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-REC.\n"
        "           05 FILLER PIC X(5).\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    rec = ws.get_data_description_entry("WS-REC")
    filler = rec.data_description_entries[0]
    assert filler.filler is True
    assert filler.filler_number is not None


def test_multiple_clauses_on_one_entry(analyze):
    """An entry can carry several clauses simultaneously."""
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-X PIC 9(5) VALUE 0 USAGE COMP BLANK WHEN ZERO.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    ws = analyze(src).compilation_unit.program_unit.data_division.working_storage_section
    entry = ws.get_data_description_entry("WS-X")
    assert entry.picture_clause is not None
    assert entry.value_clause is not None
    assert entry.usage_clause is not None
    assert entry.blank_when_zero_clause is not None


# === FD clause tests =======================================================

def _fd_entry(analyze, fd_clauses, data_items=None):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       INPUT-OUTPUT SECTION.\n"
        "       FILE-CONTROL.\n"
        "           SELECT MY-FILE ASSIGN TO 'X'.\n"
        "       DATA DIVISION.\n"
        "       FILE SECTION.\n"
        f"       FD  MY-FILE {fd_clauses}.\n"
        + (data_items or "       01  MY-REC PIC X.\n")
        + "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    fs = analyze(src).compilation_unit.program_unit.data_division.file_section
    return fs.file_description_entries[0]


def test_fd_no_clauses(analyze):
    fd = _fd_entry(analyze, "LABEL RECORDS ARE STANDARD")
    assert fd.name == "MY-FILE"
    assert fd.label_records_clause is not None


def test_fd_block_contains(analyze):
    fd = _fd_entry(analyze, "BLOCK CONTAINS 10 RECORDS")
    assert fd.block_contains_clause is not None
    assert fd.block_contains_clause.from_ is not None


def test_fd_code_set(analyze):
    fd = _fd_entry(analyze, "CODE-SET IS MY-ALPHABET")
    assert fd.code_set_clause is not None
    assert fd.code_set_clause.alphabet_name is not None


def test_fd_data_records(analyze):
    fd = _fd_entry(analyze, "DATA RECORD IS MY-REC")
    assert fd.data_records_clause is not None
    assert len(fd.data_records_clause.data_calls) >= 1


def test_fd_label_records_standard(analyze):
    fd = _fd_entry(analyze, "LABEL RECORDS ARE STANDARD")
    assert fd.label_records_clause is not None


def test_fd_record_contains(analyze):
    fd = _fd_entry(analyze, "RECORD CONTAINS 80 LABEL RECORDS ARE STANDARD")
    assert fd.record_contains_clause is not None


# === DataDescriptionEntryExecSql ===========================================

def test_data_description_exec_sql(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "           EXEC SQL INCLUDE SQLCA END-EXEC.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    dd = analyze(src).compilation_unit.program_unit.data_division
    ws = dd.working_storage_section
    # Should have two entries: the exec-sql entry and the group entry
    assert len(ws.data_description_entries) >= 2
    exec_entry = ws.data_description_entries[0]
    from cobol_py.asg.data import DataDescriptionEntryExecSql
    assert isinstance(exec_entry, DataDescriptionEntryExecSql)
    assert exec_entry.data_description_entry_type.name == "EXEC_SQL"
    assert "INCLUDE SQLCA" in exec_entry.exec_sql_text.upper()
    assert "EXECSQL" not in exec_entry.exec_sql_text
