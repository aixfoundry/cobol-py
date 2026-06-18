"""Integration tests for the full proleap-style pipeline.

These exercise the public surface of :mod:`cobol_py`:

* :class:`CobolParserRunner` - preprocess -> ``Cobol.g4`` parse -> ``startRule`` AST.
* :class:`CobolPreprocessorImpl` - the COPY / REPLACE / EXEC transforms, asserted
  on the preprocessed text (the same way proleap's own integration tests do).

The fixture programs live under ``tests/fixtures`` and cover the three source
formats (FIXED / TANDEM / VARIABLE) plus every preprocessor construct.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cobol_py import (
    CobolParserException,
    CobolParserRunner,
    CobolPreprocessorException,
    CobolPreprocessorImpl,
    CobolSourceFormatEnum,
)
from cobol_py.params import CobolParserParams

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# --- helpers -----------------------------------------------------------------


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _preprocess(name: str, params: CobolParserParams) -> str:
    return CobolPreprocessorImpl().process(_read(name), params)


def _parse(name: str, params: CobolParserParams):
    return CobolParserRunner().parse(_read(name), params)


# --- end-to-end parse (preprocess + grammar) --------------------------------


@pytest.mark.parametrize(
    ("name", "fmt"),
    [
        ("hello.cbl", CobolSourceFormatEnum.FIXED),
        ("replace.cbl", CobolSourceFormatEnum.FIXED),
        ("exec_sql.cbl", CobolSourceFormatEnum.FIXED),
        ("exec_cics.cbl", CobolSourceFormatEnum.FIXED),
        ("tandem.cbl", CobolSourceFormatEnum.TANDEM),
        ("variable.cbl", CobolSourceFormatEnum.VARIABLE),
    ],
)
def test_fixture_parses_to_start_rule(name: str, fmt: CobolSourceFormatEnum):
    # Arrange
    params = CobolParserParams(format=fmt)

    # Act
    ast = _parse(name, params)

    # Assert - the entry rule of Cobol.g4 is startRule.
    assert ast is not None
    assert type(ast).__name__ == "StartRuleContext"


def test_parse_minimal_program_has_identification_division():
    # Arrange
    params = CobolParserParams(format=CobolSourceFormatEnum.FIXED)

    # Act
    ast = _parse("hello.cbl", params)

    # Assert - the tree text contains the divisions we authored.
    tree_text = ast.getText()
    assert "IDENTIFICATIONDIVISION" in tree_text
    assert "PROCEDUREDIVISION" in tree_text


def test_parse_file_returns_ast(fixtures_dir: Path):
    # Arrange / Act
    ast = CobolParserRunner().parse_file(
        str(fixtures_dir / "hello.cbl"), CobolSourceFormatEnum.FIXED
    )

    # Assert
    assert type(ast).__name__ == "StartRuleContext"


def test_parse_file_missing_raises():
    # Arrange
    missing = FIXTURES / "does-not-exist.cbl"

    # Act / Assert
    with pytest.raises(CobolParserException, match="Could not find file"):
        CobolParserRunner().parse_file(str(missing), CobolSourceFormatEnum.FIXED)


def test_invalid_source_raises_syntax_error():
    # Arrange - a line that is valid FIXED format but is not COBOL.
    params = CobolParserParams(format=CobolSourceFormatEnum.FIXED)

    # Act / Assert
    with pytest.raises(CobolParserException, match="syntax error"):
        CobolParserRunner().parse("       THIS IS NOT COBOL AT ALL.\n", params)


# --- preprocessor transforms (asserted on the rewritten text) ----------------


def test_preprocessor_applies_replace_pseudo_text():
    # Arrange
    params = CobolParserParams(format=CobolSourceFormatEnum.FIXED)

    # Act
    preprocessed = _preprocess("replace.cbl", params)

    # Assert - ==PAYROLL== was rewritten to ==SALARY== everywhere.
    assert "SALARY" in preprocessed
    assert "PAYROLL" not in preprocessed


def test_preprocessor_tags_exec_sql():
    # Arrange
    params = CobolParserParams(format=CobolSourceFormatEnum.FIXED)

    # Act
    preprocessed = _preprocess("exec_sql.cbl", params)

    # Assert - each EXEC SQL line is tagged and END-EXEC carries the } marker,
    # which the main grammar's lexer turns into the EXECSQLLINE tokens.
    assert "*>EXECSQL" in preprocessed
    assert "}" in preprocessed


def test_preprocessor_inlines_copybook(fixtures_dir: Path):
    # Arrange
    params = CobolParserParams(
        format=CobolSourceFormatEnum.FIXED,
        copy_book_directories=[fixtures_dir],
    )

    # Act
    preprocessed = _preprocess("copy_main.cbl", params)

    # Assert - the 01 WS-COPY record from MYCOPY.CPY was inlined.
    assert "WS-COPY" in preprocessed


def test_copybook_not_found_raises(fixtures_dir: Path):
    # Arrange - no copy book directory configured, so MYCOPY cannot resolve.
    params = CobolParserParams(format=CobolSourceFormatEnum.FIXED)

    # Act / Assert
    with pytest.raises(CobolPreprocessorException, match="Could not find copy book MYCOPY"):
        CobolParserRunner().parse(_read("copy_main.cbl"), params)


# --- source-format handling --------------------------------------------------


def test_variable_format_preserves_area_b_past_column_72():
    """VARIABLE format must keep area B content beyond column 72 (FIXED would
    spill it into the dropped comment area and truncate the literal)."""
    # Arrange
    params = CobolParserParams(format=CobolSourceFormatEnum.VARIABLE)

    # Act
    preprocessed = _preprocess("variable.cbl", params)

    # Assert - the long DISPLAY literal survives intact.
    assert "does not truncate" in preprocessed


def test_unparseable_line_raises_with_format_hint():
    # Arrange - TANDEM format cannot make sense of a 7-char sequence area.
    params = CobolParserParams(format=CobolSourceFormatEnum.TANDEM)

    # Act / Assert
    with pytest.raises(CobolPreprocessorException, match="correct line format"):
        CobolPreprocessorImpl().process(
            "0000000 IDENTIFICATION DIVISION.\n", params
        )
