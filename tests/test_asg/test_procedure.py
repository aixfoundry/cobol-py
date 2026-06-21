"""Phase B: identification division + procedure-division structure."""

from __future__ import annotations


def test_program_id_name(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. HELLO.\n"
        "       PROCEDURE DIVISION.\n"
        "           STOP RUN.\n"
    )
    # Act
    pu = analyze(src).compilation_unit.program_unit
    # Assert
    assert pu.identification_division.program_id_paragraph.name == "HELLO"


def test_sections_and_paragraphs(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. X.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           DISPLAY 'a'.\n"
        "       INIT-SECTION SECTION.\n"
        "       INIT-PARA.\n"
        "           DISPLAY 'b'.\n"
        "           STOP RUN.\n"
    )
    # Act
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    # Assert
    assert [s.name for s in pd.sections] == ["INIT-SECTION"]
    assert [p.name for p in pd.paragraphs] == ["MAIN-PARA", "INIT-PARA"]


def test_root_paragraphs_exclude_sectioned(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. X.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           STOP RUN.\n"
        "       INIT-SECTION SECTION.\n"
        "       INIT-PARA.\n"
        "           STOP RUN.\n"
    )
    # Act
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    # Assert
    assert [p.name for p in pd.root_paragraphs] == ["MAIN-PARA"]


def test_paragraph_links_to_section(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. X.\n"
        "       PROCEDURE DIVISION.\n"
        "       INIT-SECTION SECTION.\n"
        "       INIT-PARA.\n"
        "           STOP RUN.\n"
    )
    # Act
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    init_para = pd.get_paragraph("INIT-PARA")
    # Assert
    assert init_para is not None
    assert init_para.section is pd.get_section("INIT-SECTION")


def test_get_paragraph_by_name(analyze):
    # Arrange
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. X.\n"
        "       PROCEDURE DIVISION.\n"
        "       PARA-ONE.\n"
        "           STOP RUN.\n"
    )
    # Act
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    # Assert
    assert pd.get_paragraph("PARA-ONE") is not None
    assert pd.get_paragraph("para-one") is not None  # symbol lookup is case-insensitive
    assert pd.get_paragraph("NOPE") is None
