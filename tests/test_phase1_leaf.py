"""Unit tests for Phase 1 leaf types and helpers (exceptions, params, utils,
CobolLine, CobolSourceFormatEnum, ThrowingErrorListener).

AAA pattern. These assert the exact behaviour ported from proleap's Java
source rather than round-trip equivalence.
"""

from __future__ import annotations

import pytest

from cobol_py.exceptions import CobolParserException, CobolPreprocessorException
from cobol_py.params import CobolDialect, CobolParserParams
from cobol_py.error_listener import ThrowingErrorListener
from cobol_py.preprocessor.constants import (
    COMMENT_TAG,
    EXEC_CICS_TAG,
    EXEC_END_TAG,
    EXEC_SQL_TAG,
    EXEC_SQLIMS_TAG,
    CobolSourceFormatEnum,
)
from cobol_py.preprocessor.line import CobolLine, CobolLineTypeEnum
from cobol_py.preprocessor.string_utils import trim_quotes
from cobol_py.util import filename_utils, string_utils


# --- exceptions --------------------------------------------------------------


def test_preprocessor_exception_is_runtime_and_carries_message():
    exc = CobolPreprocessorException("boom")
    assert isinstance(exc, RuntimeError)
    assert exc.message == "boom"
    assert str(exc) == "boom"


def test_parser_exception_is_runtime_and_carries_message():
    exc = CobolParserException("bad parse")
    assert isinstance(exc, RuntimeError)
    assert exc.message == "bad parse"


# --- params ------------------------------------------------------------------


def test_dialect_members_match_java_enum():
    assert {d.name for d in CobolDialect} == {"ANSI85", "MF", "OSVS"}


def test_params_defaults():
    # The copy-book lookup fields default to None (matching the Java bean's
    # null defaults) — the finders branch on `is not None`, so an empty list
    # would wrongly take the extension-matching path and never match.
    params = CobolParserParams()
    assert params.charset == "utf-8"
    assert params.copy_book_directories is None
    assert params.copy_book_extensions is None
    assert params.copy_book_files is None
    assert params.dialect is None
    assert params.format is None
    assert params.ignore_syntax_errors is False


def test_params_copy_book_fields_are_independent():
    # defaults are None, but assigned lists must not leak across instances.
    a = CobolParserParams()
    b = CobolParserParams()
    a.copy_book_extensions = [".cbl"]
    assert a.copy_book_extensions == [".cbl"]
    assert b.copy_book_extensions is None


# --- source format enum ------------------------------------------------------


def test_format_multiline_flags():
    assert CobolSourceFormatEnum.FIXED.comment_entry_multi_line is True
    assert CobolSourceFormatEnum.TANDEM.comment_entry_multi_line is False
    assert CobolSourceFormatEnum.VARIABLE.comment_entry_multi_line is True
    assert CobolSourceFormatEnum.FREE.comment_entry_multi_line is False


@pytest.mark.parametrize(
    "format_cls", list(CobolSourceFormatEnum), ids=[f.name for f in CobolSourceFormatEnum]
)
def test_format_regex_is_full_match(format_cls):
    # Java uses Matcher.matches() == full match. A normal short line matches.
    assert format_cls.pattern.fullmatch('       DISPLAY "X"') is not None


def test_fixed_format_groups_split_areas():
    # sequence(6) indicator(1) areaA(4) areaB(..) comment(..)
    m = CobolSourceFormatEnum.FIXED.pattern.fullmatch("000100*MOVE 1 TO X")
    assert m is not None
    seq, indicator, area_a, area_b, _comment = m.groups()
    assert seq == "000100"
    assert indicator == "*"
    assert area_a == "MOVE"
    # area B greedily takes the rest within its 61-char bound
    assert area_b == " 1 TO X"


def test_tandem_format_has_empty_sequence_area():
    m = CobolSourceFormatEnum.TANDEM.pattern.fullmatch(' DISPLAY "X"')
    assert m is not None
    seq, indicator, area_a, area_b, comment = m.groups()
    assert seq == ""
    assert indicator == " "
    assert comment == ""


def test_free_format_regex_produces_normal_line():
    """FREE format captures the entire line as content area B, with empty seq
    and empty indicator (falls through to NORMAL in _determine_type)."""
    m = CobolSourceFormatEnum.FREE.pattern.fullmatch("DISPLAY 'HELLO'")
    assert m is not None
    seq, indicator, area_a, area_b, comment = m.groups()
    assert seq == ""
    assert indicator == ""
    assert area_a == "DISP"
    assert area_b == "LAY 'HELLO'"
    assert comment == ""


def test_free_format_regex_handles_empty_line():
    m = CobolSourceFormatEnum.FREE.pattern.fullmatch("")
    assert m is not None
    seq, indicator, area_a, area_b, comment = m.groups()
    assert seq == ""
    assert indicator == ""
    assert area_a == ""
    assert area_b == ""
    assert comment == ""


def test_free_format_regex_handles_directive_line():
    """FREE format regex should match >>SOURCe format is FREE as a normal line;
    the >> override in parse_line() will reclassify it later."""
    m = CobolSourceFormatEnum.FREE.pattern.fullmatch(">>SOURCE FORMAT IS FREE")
    assert m is not None
    seq, indicator, area_a, area_b, comment = m.groups()
    assert seq == ""
    assert indicator == ""
    assert area_a == ">>SO"
    assert area_b == "URCE FORMAT IS FREE"


def test_free_format_regex_handles_indented_code():
    """FREE format preserves leading whitespace as part of content."""
    m = CobolSourceFormatEnum.FREE.pattern.fullmatch("    DISPLAY 'X'.")
    assert m is not None
    seq, indicator, area_a, area_b, comment = m.groups()
    assert seq == ""
    assert indicator == ""
    assert area_a == "    "  # leading whitespace is in area A
    assert area_b == "DISPLAY 'X'."


# --- preprocessor constants (tags) ------------------------------------------


def test_tags_match_proleap_values():
    assert COMMENT_TAG == "*>"
    assert EXEC_SQL_TAG == "*>EXECSQL"
    assert EXEC_CICS_TAG == "*>EXECCICS"
    assert EXEC_SQLIMS_TAG == "*>EXECSQLIMS"
    assert EXEC_END_TAG == "}"


# --- trim_quotes -------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('"BOOK1"', "BOOK1"),
        ("'BOOK1'", "BOOK1"),
        ('"BOOK1', "BOOK1"),  # only leading quote stripped
        ('BOOK1"', "BOOK1"),  # only trailing quote stripped
        ("BOOK1", "BOOK1"),
    ],
)
def test_trim_quotes(raw, expected):
    assert trim_quotes(raw) == expected


# --- FilenameUtils -----------------------------------------------------------


@pytest.mark.parametrize(
    "path,base,ext,name",
    [
        ("/tmp/BOOK1.CPY", "BOOK1", "CPY", "BOOK1.CPY"),
        ("BOOK1", "BOOK1", "", "BOOK1"),
        ("a/b/c.cbl", "c", "cbl", "c.cbl"),
        ("C:\\dir\\x.cpy", "x", "cpy", "x.cpy"),
    ],
)
def test_filename_utils(path, base, ext, name):
    assert filename_utils.get_base_name(path) == base
    assert filename_utils.get_extension(path) == ext
    assert filename_utils.get_name(path) == name


def test_filename_utils_none_inputs():
    assert filename_utils.get_base_name(None) is None
    assert filename_utils.get_extension(None) is None
    assert filename_utils.get_name(None) is None
    assert filename_utils.remove_extension(None) is None


def test_filename_utils_no_extension_after_separator():
    # extension dot before the separator must not count
    assert filename_utils.get_extension("/etc.d/file") == ""
    assert filename_utils.get_base_name("/etc.d/file") == "file"


# --- StringUtils -------------------------------------------------------------


def test_string_utils_helpers():
    assert string_utils.capitalize("hello") == "Hello"
    assert string_utils.capitalize("") == ""
    assert string_utils.capitalize(None) is None
    assert string_utils.right_pad("ab", 5) == "ab   "
    assert string_utils.left_pad("ab", 5) == "   ab"
    assert string_utils.right_pad("ab", 5, "0") == "ab000"
    assert string_utils.count_matches("a,b,c,d", ",") == 3
    assert string_utils.substring_before("a.b.c", ".") == "a"
    assert string_utils.substring_after("a.b.c", ".") == "b.c"
    assert string_utils.substring_before("abc", ".") == "abc"
    assert string_utils.substring_after("abc", ".") == ""
    assert string_utils.lowercase_first_letter("DISPLAY") == "dISPLAY"


# --- CobolLine ---------------------------------------------------------------


def _line(content_area_b: str = 'DISPLAY "X"', indicator: str = " ") -> CobolLine:
    return CobolLine.new_cobol_line(
        sequence_area=" " * 6,
        indicator_area=indicator,
        content_area_a="    ",
        content_area_b=content_area_b,
        comment_area="",
        format=CobolSourceFormatEnum.FIXED,
        dialect=CobolDialect.MF,
        number=1,
        type=CobolLineTypeEnum.NORMAL,
    )


def test_line_type_enum_members():
    assert {t.name for t in CobolLineTypeEnum} == {
        "BLANK",
        "COMMENT",
        "COMPILER_DIRECTIVE",
        "CONTINUATION",
        "DEBUG",
        "NORMAL",
    }


def test_new_cobol_line_originals_equal_current():
    line = _line()
    assert line.get_sequence_area() == line.get_sequence_area_original()
    assert line.get_content_area() == line.get_content_area_original()
    assert line.get_indicator_area() == line.get_indicator_area_original()


def test_serialize_concatenates_areas():
    line = _line()
    assert line.serialize() == '           DISPLAY "X"'


def test_get_content_area_concatenates_a_and_b():
    line = _line()
    assert line.get_content_area() == '    DISPLAY "X"'


def test_blank_sequence_area_is_six_spaces_except_tandem_and_free():
    assert CobolLine.create_blank_sequence_area(CobolSourceFormatEnum.FIXED) == " " * 6
    assert CobolLine.create_blank_sequence_area(CobolSourceFormatEnum.TANDEM) == ""
    assert CobolLine.create_blank_sequence_area(CobolSourceFormatEnum.FREE) == ""


def test_copy_with_content_area_splits_a_and_b():
    line = _line()
    # content longer than 4 chars -> first 4 to area A, rest to area B
    copy = CobolLine.copy_with_content_area("MOVE 1 TO X", line)
    assert copy.get_content_area_a() == "MOVE"
    assert copy.get_content_area_b() == " 1 TO X"
    # originals retained from source line
    assert copy.get_content_area_a_original() == "    "
    assert copy.get_content_area_b_original() == 'DISPLAY "X"'


def test_copy_with_indicator_and_content_area():
    line = _line()
    copy = CobolLine.copy_with_indicator_and_content_area("-", "MOVE 1", line)
    assert copy.get_indicator_area() == "-"
    assert copy.get_content_area() == "MOVE 1"


def test_linked_list_wiring_is_bidirectional():
    a = _line(content_area_b="A")
    b = _line(content_area_b="B")
    a.set_successor(b)
    assert a.get_successor() is b
    assert b.get_predecessor() is a


def test_str_returns_serialize():
    line = _line()
    assert str(line) == line.serialize()


# --- ThrowingErrorListener ---------------------------------------------------


def test_throwing_error_listener_raises_parser_exception():
    listener = ThrowingErrorListener()
    with pytest.raises(CobolParserException) as exc_info:
        listener.syntaxError(None, None, 7, 3, "mismatched input", None)
    assert "7:3" in exc_info.value.message
    assert "mismatched input" in exc_info.value.message
