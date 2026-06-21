"""Phase E: environment division — file-control structure."""

from __future__ import annotations


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
