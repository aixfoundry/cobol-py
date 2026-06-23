"""Phase E: environment division — file-control structure and clause decomposition."""

from __future__ import annotations

from cobol_py.asg import (
    AccessMode,
    AccessModeClause,
    AssignClause,
    FileControlEntry,
    FileStatusClause,
    OrganizationClause,
    OrganizationMode,
    RecordKeyClause,
    RelativeKeyClause,
    ReserveClause,
    SelectClause,
)


_ENV_SRC = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. T.\n"
    "       ENVIRONMENT DIVISION.\n"
    "       INPUT-OUTPUT SECTION.\n"
    "       FILE-CONTROL.\n"
    "           SELECT IN-FILE ASSIGN TO 'IN.DAT'.\n"
    "           SELECT OUT-FILE ASSIGN TO 'OUT.DAT'.\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  WS-X PIC 9.\n"
    "       PROCEDURE DIVISION.\n"
    "           STOP RUN.\n"
)


def _select_entry(analyze, file_control_line, data_division=""):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       INPUT-OUTPUT SECTION.\n"
        "       FILE-CONTROL.\n"
        f"           {file_control_line}\n"
        + (data_division or "       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01  WS-A PIC 9.\n")
        + "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    fcp = analyze(src).compilation_unit.program_unit.environment_division.input_output_section.file_control_paragraph
    return fcp.file_control_entries[0]


def test_file_control_entries_built(analyze):
    # Act
    ed = analyze(_ENV_SRC).compilation_unit.program_unit.environment_division
    fcp = ed.input_output_section.file_control_paragraph
    # Assert
    assert fcp is not None
    assert {e.name for e in fcp.file_control_entries} == {"IN-FILE", "OUT-FILE"}


def test_file_control_entry_lookup(analyze):
    # Act
    fcp = analyze(_ENV_SRC).compilation_unit.program_unit.environment_division.input_output_section.file_control_paragraph
    # Assert
    assert fcp.get_file_control_entry("IN-FILE") is not None
    assert fcp.get_file_control_entry("in-file") is not None  # case-insensitive
    assert fcp.get_file_control_entry("NOPE") is None


def test_environment_division_linked_on_program_unit(analyze):
    # Act
    pu = analyze(_ENV_SRC).compilation_unit.program_unit
    # Assert
    assert pu.environment_division is not None
    assert pu.environment_division.input_output_section is not None


# === Phase E2: file-control clause decomposition ============================

def test_select_optional(analyze):
    entry = _select_entry(analyze, "SELECT OPTIONAL MY-FILE ASSIGN TO 'X'.")
    assert entry.select_clause is not None
    assert isinstance(entry.select_clause, SelectClause)
    assert entry.select_clause.optional is True


def test_assign_clause(analyze):
    entry = _select_entry(analyze, "SELECT MY-FILE ASSIGN TO 'MY.DAT'.")
    assert entry.assign_clause is not None
    assert isinstance(entry.assign_clause, AssignClause)
    assert entry.assign_clause.to_value_stmt is not None


def test_organization_indexed(analyze):
    entry = _select_entry(analyze, "SELECT MY-FILE ASSIGN TO 'X' ORGANIZATION IS INDEXED.")
    assert entry.organization_clause is not None
    assert isinstance(entry.organization_clause, OrganizationClause)
    assert entry.organization_clause.mode is OrganizationMode.INDEXED


def test_access_mode_random(analyze):
    entry = _select_entry(analyze, "SELECT MY-FILE ASSIGN TO 'X' ACCESS MODE IS RANDOM.")
    assert entry.access_mode_clause is not None
    assert isinstance(entry.access_mode_clause, AccessModeClause)
    assert entry.access_mode_clause.mode is AccessMode.RANDOM


def test_file_status_clause(analyze):
    entry = _select_entry(analyze, "SELECT MY-FILE ASSIGN TO 'X' FILE STATUS IS WS-A WS-B.",
                          data_division="       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01  WS-A PIC X(2).\n       01  WS-B PIC X(2).\n")
    assert entry.file_status_clause is not None
    assert isinstance(entry.file_status_clause, FileStatusClause)
    assert entry.file_status_clause.data_call is not None
    assert entry.file_status_clause.data_call2 is not None


def test_record_key_clause(analyze):
    entry = _select_entry(analyze, "SELECT MY-FILE ASSIGN TO 'X' RECORD KEY IS WS-KEY.",
                          data_division="       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01  WS-KEY PIC 9.\n")
    assert entry.record_key_clause is not None
    assert isinstance(entry.record_key_clause, RecordKeyClause)
    assert entry.record_key_clause.record_key_call is not None


def test_relative_key_clause(analyze):
    entry = _select_entry(analyze, "SELECT MY-FILE ASSIGN TO 'X' RELATIVE KEY IS WS-KEY.",
                          data_division="       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01  WS-KEY PIC 9.\n")
    assert entry.relative_key_clause is not None
    assert isinstance(entry.relative_key_clause, RelativeKeyClause)


def test_reserve_clause(analyze):
    entry = _select_entry(analyze, "SELECT MY-FILE ASSIGN TO 'X' RESERVE 3 AREAS.")
    assert entry.reserve_clause is not None
    assert isinstance(entry.reserve_clause, ReserveClause)


# === Configuration section tests ============================================

def test_source_computer_paragraph(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       CONFIGURATION SECTION.\n"
        "       SOURCE-COMPUTER. IBM-370.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    cs = analyze(src).compilation_unit.program_unit.environment_division.configuration_section
    assert cs is not None
    assert cs.source_computer_paragraph is not None
    assert cs.source_computer_paragraph.name.upper() == "IBM-370"


def test_source_computer_with_debugging(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       CONFIGURATION SECTION.\n"
        "       SOURCE-COMPUTER. IBM-370 WITH DEBUGGING MODE.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    cs = analyze(src).compilation_unit.program_unit.environment_division.configuration_section
    assert cs.source_computer_paragraph.debugging is True


def test_object_computer_paragraph(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       CONFIGURATION SECTION.\n"
        "       OBJECT-COMPUTER. IBM-370 MEMORY SIZE 4096.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    cs = analyze(src).compilation_unit.program_unit.environment_division.configuration_section
    assert cs.object_computer_paragraph is not None
    assert cs.object_computer_paragraph.memory_size_clause is not None


# === Special names tests ===================================================

def test_special_names_alphabet(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       CONFIGURATION SECTION.\n"
        "       SPECIAL-NAMES.\n"
        "           ALPHABET MY-ABC IS STANDARD-1.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    sp = analyze(src).compilation_unit.program_unit.environment_division.special_names_paragraph
    assert sp is not None
    assert len(sp.alphabet_clauses) == 1
    assert sp.alphabet_clauses[0].alphabet_name == "MY-ABC"


def test_special_names_decimal_point_comma(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       CONFIGURATION SECTION.\n"
        "       SPECIAL-NAMES.\n"
        "           DECIMAL-POINT IS COMMA.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    sp = analyze(src).compilation_unit.program_unit.environment_division.special_names_paragraph
    assert sp.decimal_point_clause is not None
    assert sp.decimal_point_clause.is_comma is True


def test_special_names_currency_sign(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       CONFIGURATION SECTION.\n"
        "       SPECIAL-NAMES.\n"
        "           CURRENCY SIGN IS '$'.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    sp = analyze(src).compilation_unit.program_unit.environment_division.special_names_paragraph
    assert sp.currency_sign_clause is not None
