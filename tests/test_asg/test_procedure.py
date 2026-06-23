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


# --- Procedure division USING / GIVING clauses -------------------------------

def test_procedure_division_using_by_reference(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. X.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       01  WS-B PIC 9.\n"
        "       PROCEDURE DIVISION USING WS-A WS-B.\n"
        "           STOP RUN.\n"
    )
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    assert pd.using_clause is not None
    uc = pd.using_clause
    # Grammar groups contiguous identifiers under one ByReferencePhrase:
    # USING WS-A WS-B → 1 UsingParameter → ByReferencePhrase with 2 ByReference entries
    assert len(uc.using_parameters) == 1
    assert uc.using_parameters[0].using_parameter_type.name == "REFERENCE"
    brp = uc.using_parameters[0].by_reference_phrase
    assert brp is not None
    assert len(brp.by_references) == 2
    assert brp.by_references[0].reference_call is not None
    assert brp.by_references[1].reference_call is not None


def test_procedure_division_using_by_value(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. X.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-X PIC 9.\n"
        "       PROCEDURE DIVISION USING BY VALUE WS-X.\n"
        "           STOP RUN.\n"
    )
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    assert pd.using_clause is not None
    uc = pd.using_clause
    assert len(uc.using_parameters) == 1
    assert uc.using_parameters[0].using_parameter_type.name == "VALUE"
    bvp = uc.using_parameters[0].by_value_phrase
    assert bvp is not None
    assert len(bvp.by_values) == 1
    assert bvp.by_values[0].value_value_stmt is not None


def test_procedure_division_using_by_reference_optional(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. X.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       PROCEDURE DIVISION USING BY REFERENCE OPTIONAL WS-A.\n"
        "           STOP RUN.\n"
    )
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    uc = pd.using_clause
    brp = uc.using_parameters[0].by_reference_phrase
    assert brp.by_references[0].optional is True


def test_procedure_division_using_mixed(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. X.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       01  WS-B PIC 9.\n"
        "       PROCEDURE DIVISION USING BY REFERENCE WS-A BY VALUE WS-B.\n"
        "           STOP RUN.\n"
    )
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    uc = pd.using_clause
    assert len(uc.using_parameters) == 2
    assert uc.using_parameters[0].using_parameter_type.name == "REFERENCE"
    assert uc.using_parameters[1].using_parameter_type.name == "VALUE"


def test_procedure_division_giving_clause(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. X.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-RES PIC 9.\n"
        "       PROCEDURE DIVISION GIVING WS-RES.\n"
        "           STOP RUN.\n"
    )
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    assert pd.giving_clause is not None
    assert pd.giving_clause.giving_call is not None


def test_procedure_division_using_and_giving(analyze):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. X.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01  WS-A PIC 9.\n"
        "       01  WS-B PIC 9.\n"
        "       01  WS-RES PIC 9.\n"
        "       PROCEDURE DIVISION USING WS-A WS-B GIVING WS-RES.\n"
        "           STOP RUN.\n"
    )
    pd = analyze(src).compilation_unit.program_unit.procedure_division
    assert pd.using_clause is not None
    # USING WS-A WS-B → 1 UsingParameter → ByReferencePhrase with 2 ByReference entries
    assert len(pd.using_clause.using_parameters) == 1
    assert len(pd.using_clause.using_parameters[0].by_reference_phrase.by_references) == 2
    assert pd.giving_clause is not None
    assert pd.giving_clause.giving_call is not None
