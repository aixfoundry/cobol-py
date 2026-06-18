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
from cobol_py.preprocessor.line_reader import CobolLineReaderImpl
from cobol_py.preprocessor.line_writer import CobolLineWriterImpl

FIXED = CobolSourceFormatEnum.FIXED
TANDEM = CobolSourceFormatEnum.TANDEM


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
        CobolLineReaderImpl().parse_line("123456XABC", 4, _params())
    assert "line 5" in exc_info.value.message


def test_reader_split_matches_java_scanner_no_trailing_blank():
    lines = CobolLineReaderImpl().process_lines("A\nB\n", _params())
    assert len(lines) == 2
    empty = CobolLineReaderImpl().process_lines("", _params())
    assert empty == []


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
