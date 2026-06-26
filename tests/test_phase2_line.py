"""Unit tests for Phase 2 — the line sub-pipeline (reader, indicator processor,
inline-comment normalizer, comment-entries marker, writer).

Inputs are crafted so each proleap transform is exercised in isolation.
"""

from __future__ import annotations

import pytest

from cobol_py.exceptions import CobolPreprocessorException
from cobol_py.params import CobolDialect, CobolParserParams
from cobol_py.preprocessor.comment_entries_marker import CobolCommentEntriesMarkerImpl
from cobol_py.preprocessor.constants import CobolSourceFormatEnum
from cobol_py.preprocessor.inline_comment_entries_normalizer import (
    CobolInlineCommentEntriesNormalizerImpl,
)
from cobol_py.preprocessor.line import CobolLine, CobolLineTypeEnum
from cobol_py.preprocessor.line_indicator_processor import (
    CobolLineIndicatorProcessorImpl,
)
from cobol_py.preprocessor.line_reader import CobolLineReaderImpl, _join_amp_continuation
from cobol_py.preprocessor.line_writer import CobolLineWriterImpl

FIXED = CobolSourceFormatEnum.FIXED
TANDEM = CobolSourceFormatEnum.TANDEM
FREE = CobolSourceFormatEnum.FREE


def _params(format=CobolSourceFormatEnum.FIXED, dialect=CobolDialect.MF) -> CobolParserParams:
    return CobolParserParams(format=format, dialect=dialect)


def _line(
    content,
    *,
    indicator=" ",
    fmt=CobolSourceFormatEnum.FIXED,
    dialect=CobolDialect.MF,
    number=0,
    type_=CobolLineTypeEnum.NORMAL,
):
    """Build a CobolLine whose content area is split A(4)/B(rest)."""
    return CobolLine.new_cobol_line(
        sequence_area=" " * 6,
        indicator_area=indicator,
        content_area_a=content[:4],
        content_area_b=content[4:],
        comment_area="",
        format=fmt,
        dialect=dialect,
        number=number,
        type=type_,
    )


# --- line reader ------------------------------------------------------------


def test_reader_classifies_each_indicator_type():
    src = (
        "000001 IDENTIFICATION DIVISION.\n"
        "000002*COMMENT LINE\n"
        "000003/SLASH COMMENT\n"
        "000004-CONTINUATION\n"
        "000005DDEBUG LINE\n"
        "000006ddebug lower\n"
        "000007$SET SOURCEFORMAT\n"
    )
    lines = CobolLineReaderImpl().process_lines(src, _params())
    types = [l.get_type() for l in lines]
    assert types == [
        CobolLineTypeEnum.NORMAL,
        CobolLineTypeEnum.COMMENT,
        CobolLineTypeEnum.COMMENT,
        CobolLineTypeEnum.CONTINUATION,
        CobolLineTypeEnum.DEBUG,
        CobolLineTypeEnum.DEBUG,
        CobolLineTypeEnum.COMPILER_DIRECTIVE,
    ]


def test_reader_builds_doubly_linked_list():
    src = "000001 A\n000002 B\n000003 C\n"
    lines = CobolLineReaderImpl().process_lines(src, _params())
    assert lines[0].get_predecessor() is None
    assert lines[0].get_successor() is lines[1]
    assert lines[1].get_predecessor() is lines[0]
    assert lines[1].get_successor() is lines[2]
    assert lines[2].get_successor() is None
    assert [l.get_number() for l in lines] == [0, 1, 2]


def test_reader_fixed_area_split():
    line = CobolLineReaderImpl().parse_line("000100*MOVE 1 TO X", 0, _params())
    assert line.get_sequence_area() == "000100"
    assert line.get_indicator_area() == "*"
    assert line.get_content_area_a() == "MOVE"
    assert line.get_content_area_b() == " 1 TO X"


def test_reader_raises_on_unparseable_line():
    with pytest.raises(CobolPreprocessorException) as exc_info:
        CobolLineReaderImpl().parse_line("123456!ABC", 4, _params())
    assert "line 5" in exc_info.value.message


def test_reader_split_matches_java_scanner_no_trailing_blank():
    lines = CobolLineReaderImpl().process_lines("A\nB\n", _params())
    assert len(lines) == 2
    empty = CobolLineReaderImpl().process_lines("", _params())
    assert empty == []


# --- free format line reader ---------------------------------------------------


def test_reader_free_format_line_is_normal():
    """FREE format lines have empty indicator → fall through to NORMAL type."""
    params = _params(format=CobolSourceFormatEnum.FREE)
    line = CobolLineReaderImpl().parse_line("DISPLAY 'HELLO'.", 0, params)
    assert line.get_type() == CobolLineTypeEnum.NORMAL
    assert line.get_indicator_area() == ""
    assert line.get_sequence_area() == ""
    assert line.get_content_area() == "DISP" + "LAY 'HELLO'."


def test_reader_free_format_compiler_directive():
    """Lines starting with '>>' (except >>D) are reclassified as COMPILER_DIRECTIVE."""
    params = _params(format=CobolSourceFormatEnum.FREE)
    line = CobolLineReaderImpl().parse_line(">>SOURCE FORMAT IS FREE", 0, params)
    assert line.get_type() == CobolLineTypeEnum.COMPILER_DIRECTIVE


def test_reader_free_format_directives():
    """Various >> directive forms (excluding >>D) should be COMPILER_DIRECTIVE."""
    params = _params(format=CobolSourceFormatEnum.FREE)
    directives = [
        ">>SOURCE FORMAT IS FREE",
        ">>SOURCE FREE",
        ">>DEFINE MYVAR AS 1",
        ">>IF MYVAR > 0",
        ">>ELSE",
        ">>END-IF",
        ">>EVALUATE",
    ]
    for d in directives:
        line = CobolLineReaderImpl().parse_line(d, 0, params)
        assert line.get_type() == CobolLineTypeEnum.COMPILER_DIRECTIVE, (
            f"Expected COMPILER_DIRECTIVE for: {d}"
        )


def test_reader_free_format_d_debug_line():
    """In FREE format, >>D lines are DEBUG (not COMPILER_DIRECTIVE), and the
    >>D prefix is stripped from content so the parser sees clean code."""
    params = _params(format=CobolSourceFormatEnum.FREE)
    line = CobolLineReaderImpl().parse_line(">>D DISPLAY 'A'", 0, params)
    assert line.get_type() == CobolLineTypeEnum.DEBUG
    assert ">>D" not in line.get_content_area()
    assert "DISPLAY 'A'" in line.get_content_area()


def test_reader_free_format_d_debug_with_indentation():
    """>>D debug lines with leading whitespace should still work."""
    params = _params(format=CobolSourceFormatEnum.FREE)
    line = CobolLineReaderImpl().parse_line("   >>D DISPLAY 'A'", 0, params)
    assert line.get_type() == CobolLineTypeEnum.DEBUG
    assert ">>D" not in line.get_content_area()
    assert "DISPLAY 'A'" in line.get_content_area()


def test_reader_free_format_d_debug_standalone():
    """>>D alone (no trailing code) is valid — the line is empty after
    stripping the prefix."""
    params = _params(format=CobolSourceFormatEnum.FREE)
    line = CobolLineReaderImpl().parse_line(">>D", 0, params)
    assert line.get_type() == CobolLineTypeEnum.DEBUG
    assert line.get_content_area() == ""


def test_reader_free_format_indented_directive():
    """>> directives with leading whitespace should still be detected."""
    params = _params(format=CobolSourceFormatEnum.FREE)
    line = CobolLineReaderImpl().parse_line("   >>SOURCE FORMAT IS FREE", 0, params)
    assert line.get_type() == CobolLineTypeEnum.COMPILER_DIRECTIVE


def test_reader_free_format_normal_line_not_misclassified():
    """Regular COBOL lines without >> prefix stay NORMAL."""
    params = _params(format=CobolSourceFormatEnum.FREE)
    line = CobolLineReaderImpl().parse_line("    DISPLAY 'A'", 0, params)
    assert line.get_type() == CobolLineTypeEnum.NORMAL
    assert "DISPLAY 'A'" in line.get_content_area()


def test_reader_free_format_single_greater_than_not_directive():
    """A single '>' (not '>>') is normal COBOL content, not a directive."""
    params = _params(format=CobolSourceFormatEnum.FREE)
    line = CobolLineReaderImpl().parse_line("IF A > B", 0, params)
    assert line.get_type() == CobolLineTypeEnum.NORMAL


# --- & continuation (free format) --------------------------------------------


def test_amp_continuation_joins_string_literal():
    """A trailing & should join with the next line; spaces before & are consumed."""
    text = 'DISPLAY "Hello &\n      &World"'
    joined = _join_amp_continuation(text)
    assert joined == 'DISPLAY "HelloWorld"'


def test_amp_continuation_without_leading_amp():
    """The leading & on the continuation line is optional."""
    text = "MOVE AFE &\n      TO LEN"
    joined = _join_amp_continuation(text)
    # Space before & is consumed per COBOL 2002 spec
    assert "AFETO LEN" in joined
    assert "&" not in joined


def test_amp_continuation_preserves_amp_inside_content():
    """A & not at end of line is regular content, not a continuation marker."""
    text = "CALL 'X' &   *> inline comment\n      CALL 'Y'"
    joined = _join_amp_continuation(text)
    assert "&" in joined  # inline & preserved (not at line end)


def test_amp_continuation_only_triggers_in_free_format():
    """process_lines in non-FREE format does NOT join & continuations."""
    from cobol_py.params import CobolParserParams
    params = CobolParserParams(format=CobolSourceFormatEnum.FIXED)
    text = "DISPLAY 'A &\n      B'"
    lines = CobolLineReaderImpl().process_lines(text, params)
    # Two separate lines: first has &, second has B
    assert lines[0].get_content_area() != lines[1].get_content_area()


def test_amp_multi_line_continuation():
    """Multiple consecutive & continuations should chain."""
    text = 'MOVE "ABC&\n      &DEF&\n      &GHI" TO X'
    joined = _join_amp_continuation(text)
    assert 'MOVE "ABCDEFGHI" TO X' == joined


# --- indicator processor ----------------------------------------------------


def test_processor_normal_right_trims_and_repairs_trailing_comma():
    line = _line("DISPLAY 1,   ", number=0)
    out = CobolLineIndicatorProcessorImpl().process_line(line)
    assert out.get_indicator_area() == " "
    assert out.get_content_area() == "DISPLAY 1, "


def test_processor_normal_semicolon_repair():
    line = _line("PERFORM A;", number=0)
    out = CobolLineIndicatorProcessorImpl().process_line(line)
    assert out.get_content_area() == "PERFORM A; "


def test_processor_comment_tag():
    line = _line("a comment", indicator="*", type_=CobolLineTypeEnum.COMMENT)
    out = CobolLineIndicatorProcessorImpl().process_line(line)
    assert out.get_indicator_area() == "*> "


def test_processor_debug_blanked():
    line = _line("DEBUG LINE", indicator="D", type_=CobolLineTypeEnum.DEBUG)
    out = CobolLineIndicatorProcessorImpl().process_line(line)
    assert out.get_indicator_area() == " "


def test_processor_compiler_directive_emptied():
    line = _line("SET SOURCEFORMAT", indicator="$", type_=CobolLineTypeEnum.COMPILER_DIRECTIVE)
    out = CobolLineIndicatorProcessorImpl().process_line(line)
    assert out.get_indicator_area() == " "
    assert out.get_content_area() == ""


def test_processor_continuation_removes_leading_quote_when_pred_ends_in_quote():
    # Branch 2: predecessor ORIGINAL content ends with a quote, and the
    # continuation (after trimming leading ws) starts with a quote -> the first
    # quote of the continuation is removed.
    pred = _line('ABC"', number=0)
    cont = _line('   "DEF', indicator="-", number=1, type_=CobolLineTypeEnum.CONTINUATION)
    pred.set_successor(cont)
    out = CobolLineIndicatorProcessorImpl().process_line(cont)
    assert out.get_content_area() == "DEF"
    assert out.get_indicator_area() == " "


def test_processor_continuation_open_literal_removes_leading_quote():
    # Branch 3: predecessor ends with an OPEN literal (a quote that is not the
    # last char), continuation starts with a quote -> leading quote removed to
    # keep the literal open. (Branch 4 -- predecessor current content ends in a
    # quote -- is unreachable on freshly-read lines because branch 2 already
    # matches the identical original-content condition.)
    pred = _line('AB"CD', number=0)
    cont = _line('   "EF"', indicator="-", number=1, type_=CobolLineTypeEnum.CONTINUATION)
    pred.set_successor(cont)
    out = CobolLineIndicatorProcessorImpl().process_line(cont)
    assert out.get_content_area() == 'EF"'
    assert out.get_indicator_area() == " "


def test_processor_continuation_fallback_trims_leading_ws():
    pred = _line("MOVE 1 TO X.", number=0)
    cont = _line("   MORE", indicator="-", number=1, type_=CobolLineTypeEnum.CONTINUATION)
    pred.set_successor(cont)
    out = CobolLineIndicatorProcessorImpl().process_line(cont)
    assert out.get_content_area() == "MORE"


def test_processor_continuation_empty_becomes_blank():
    cont = _line("   ", indicator="-", number=1, type_=CobolLineTypeEnum.CONTINUATION)
    out = CobolLineIndicatorProcessorImpl().process_line(cont)
    assert out.get_content_area() == ""


def test_processor_keeps_open_literal_untrimmed():
    line = _line('DISPLAY "open', number=0)
    cont = _line('   rest"', indicator="-", number=1, type_=CobolLineTypeEnum.CONTINUATION)
    line.set_successor(cont)
    processed = CobolLineIndicatorProcessorImpl().process_line(line)
    assert processed.get_content_area() == 'DISPLAY "open'


# --- inline comment normalizer ----------------------------------------------


def test_inline_normalizer_inserts_space_after_tag():
    line = _line("FOO*>BAR")
    out = CobolInlineCommentEntriesNormalizerImpl().process_line(line)
    assert out.get_content_area() == "FOO*> BAR"


def test_inline_normalizer_leaves_normalized_alone():
    line = _line("FOO*> BAR")
    out = CobolInlineCommentEntriesNormalizerImpl().process_line(line)
    assert out is line


# --- comment entries marker -------------------------------------------------


def test_comment_marker_escapes_trigger_fixed():
    line = _line("AUTHOR. JOHN DOE.")
    out = CobolCommentEntriesMarkerImpl().process_line(line)
    assert out.get_content_area() == "AUTHOR. *>CE JOHN DOE."


def test_comment_marker_marks_area_b_continuation_fixed():
    marker = CobolCommentEntriesMarkerImpl()
    trigger = _line("AUTHOR. SOMEONE.")
    followup = CobolLine.new_cobol_line(
        sequence_area=" " * 6,
        indicator_area=" ",
        content_area_a="    ",
        content_area_b="THIS IS A COMMENT ENTRY.",
        comment_area="",
        format=CobolSourceFormatEnum.FIXED,
        dialect=CobolDialect.MF,
        number=1,
        type=CobolLineTypeEnum.NORMAL,
    )
    marker.process_line(trigger)
    out = marker.process_line(followup)
    assert out.get_indicator_area() == "*>CE "


def test_comment_marker_area_a_line_terminates_entry_fixed():
    marker = CobolCommentEntriesMarkerImpl()
    trigger = _line("AUTHOR. SOMEONE.")
    code = _line("PROCEDURE DIVISION.", number=1)
    marker.process_line(trigger)
    out = marker.process_line(code)
    assert out.get_indicator_area() == " "


def test_comment_marker_tandem_is_single_line():
    marker = CobolCommentEntriesMarkerImpl()
    trigger = _line("AUTHOR. SOMEONE.", fmt=CobolSourceFormatEnum.TANDEM)
    followup = _line("EXTRA COMMENT", fmt=CobolSourceFormatEnum.TANDEM, number=1)
    escaped = marker.process_line(trigger)
    assert "*>CE" in escaped.get_content_area()
    out = marker.process_line(followup)
    assert out.get_indicator_area() == " "


# --- line writer ------------------------------------------------------------


def test_writer_joins_continuation_and_inserts_newlines():
    a = _line("DISPLAY", number=0)
    b = _line("WORLD", indicator="-", number=1, type_=CobolLineTypeEnum.CONTINUATION)
    c = _line("STOP", number=2)
    out = CobolLineWriterImpl().serialize([a, b, c])
    # 6 (blank seq) + 1 (indicator) = 7 spaces before each non-continuation line
    assert out == "       DISPLAY" + "WORLD" + "\n       STOP"


def test_writer_first_line_has_no_leading_newline():
    a = _line("DISPLAY", number=0)
    out = CobolLineWriterImpl().serialize([a])
    assert out.startswith("       DISPLAY")
    assert not out.startswith("\n")
