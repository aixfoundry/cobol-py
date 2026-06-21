"""Phase A: the ASG runner produces a Program with the expected skeleton."""

from __future__ import annotations

from cobol_py.asg import Program


def test_analyze_returns_program(analyze):
    # Arrange
    src = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. X.\n       PROCEDURE DIVISION.\n           STOP RUN.\n"
    # Act
    program = analyze(src)
    # Assert
    assert isinstance(program, Program)


def test_program_has_one_compilation_unit_and_program_unit(analyze):
    # Arrange
    src = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. X.\n       PROCEDURE DIVISION.\n           STOP RUN.\n"
    # Act
    program = analyze(src)
    # Assert
    assert len(program.compilation_units) == 1
    compilation_unit = program.compilation_unit
    assert compilation_unit is not None
    assert compilation_unit.program_unit is not None


def test_divisions_present(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. X.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-X PIC 9.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    # Act
    pu = analyze(src).compilation_unit.program_unit
    # Assert
    assert pu.identification_division is not None
    assert pu.environment_division is not None
    assert pu.data_division is not None
    assert pu.procedure_division is not None


def test_registry_populated(analyze):
    # Arrange
    src = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. X.\n       PROCEDURE DIVISION.\n           STOP RUN.\n"
    # Act
    program = analyze(src)
    # Assert: compilation unit, program unit, identification + procedure divisions
    # are each registered (keyed by their ctx).
    assert len(program.registry._elements) >= 4
