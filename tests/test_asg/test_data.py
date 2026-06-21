"""Phase D: data division — hierarchy and reference resolution."""

from __future__ import annotations

from cobol_py.asg import (
    CallTypeEnum,
    DataDescriptionEntryCall,
    DataDescriptionEntryGroup,
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
    assert a.picture is not None  # PIC clause captured


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
