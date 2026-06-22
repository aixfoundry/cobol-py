"""Phase C1+: arithmetic statement clause decomposition.

Covers ADD / SUBTRACT / MULTIPLY / DIVIDE / COMPUTE — the operand, type-enum,
TO/GIVING/FROM/ROUNDED/REMAINDER/COMPUTE-store detail that the bare
``_ArithmeticStatementBase`` previously deferred. Mirrors proleap's
``ScopeImpl.add{Add,Subtract,Multiply,Divide,Compute}Statement`` + the
per-verb ``*StatementImpl`` sub-builders.
"""

from __future__ import annotations

from cobol_py.asg import (
    AddStatement,
    ArithmeticValueStmt,
    CallValueStmt,
    ComputeStatement,
    DivideStatement,
    Literal,
    LiteralValueStmt,
    MoveStatement,
    MultiplyStatement,
    OnSizeErrorPhrase,
    SubtractStatement,
)


def _main_statements(analyze, body, data_items="01  WS-A PIC 9.\n       01  WS-B PIC 9.\n       01  WS-R PIC 9."):
    src = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        f"       {data_items}"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        + body
    )
    main = analyze(src).compilation_unit.program_unit.procedure_division.get_paragraph("MAIN")
    return main.statements


# --- ADD -------------------------------------------------------------------

def test_add_to_form(analyze):
    (add,) = _main_statements(analyze, "           ADD 1 TO WS-A.\n")
    assert isinstance(add, AddStatement)
    assert add.add_type is AddStatement.AddType.TO
    # one literal addend
    assert len(add.from_value_stmts) == 1
    assert isinstance(add.from_value_stmts[0], LiteralValueStmt)
    assert add.from_value_stmts[0].literal.literal_type is Literal.Type.NUMERIC
    # one receiving target, not rounded
    assert len(add.to_targets) == 1
    assert add.to_targets[0].call.name == "WS-A"
    assert add.to_targets[0].rounded is False


def test_add_to_multiple_addends_and_rounded(analyze):
    add = _main_statements(analyze, "           ADD 1 WS-B TO WS-A ROUNDED.\n")[0]
    assert add.add_type is AddStatement.AddType.TO
    assert len(add.from_value_stmts) == 2          # literal + identifier addend
    assert isinstance(add.from_value_stmts[0], LiteralValueStmt)
    assert isinstance(add.from_value_stmts[1], CallValueStmt)
    assert len(add.to_targets) == 1
    assert add.to_targets[0].call.name == "WS-A"
    assert add.to_targets[0].rounded is True


def test_add_to_giving_form(analyze):
    add = _main_statements(analyze, "           ADD 1 TO WS-A GIVING WS-B.\n")[0]
    assert add.add_type is AddStatement.AddType.TO_GIVING
    assert len(add.from_value_stmts) == 1
    assert len(add.to_value_stmts) == 1            # addToGiving is an operand
    assert isinstance(add.to_value_stmts[0], CallValueStmt)
    assert add.to_value_stmts[0].call.name == "WS-A"
    assert len(add.giving_targets) == 1
    assert add.giving_targets[0].call.name == "WS-B"


def test_add_corresponding_form(analyze):
    add = _main_statements(analyze, "           ADD CORRESPONDING WS-A TO WS-B.\n")[0]
    assert add.add_type is AddStatement.AddType.CORRESPONDING
    assert add.corresponding_from_call.name == "WS-A"
    assert add.corresponding_to_call.name == "WS-B"


# --- SUBTRACT --------------------------------------------------------------

def test_subtract_from_form(analyze):
    sub = _main_statements(analyze, "           SUBTRACT 1 FROM WS-A.\n")[0]
    assert isinstance(sub, SubtractStatement)
    assert sub.subtract_type is SubtractStatement.SubtractType.FROM
    assert len(sub.subtrahend_value_stmts) == 1
    assert len(sub.from_targets) == 1
    assert sub.from_targets[0].call.name == "WS-A"
    assert sub.from_targets[0].rounded is False


def test_subtract_from_giving_form(analyze):
    sub = _main_statements(analyze, "           SUBTRACT 1 FROM WS-A GIVING WS-B ROUNDED.\n")[0]
    assert sub.subtract_type is SubtractStatement.SubtractType.FROM_GIVING
    assert len(sub.subtrahend_value_stmts) == 1
    assert sub.from_value_stmt is not None         # subtractMinuendGiving
    assert sub.from_value_stmt.call.name == "WS-A"
    assert len(sub.giving_targets) == 1
    assert sub.giving_targets[0].call.name == "WS-B"
    assert sub.giving_targets[0].rounded is True


# --- MULTIPLY --------------------------------------------------------------

def test_multiply_by_form(analyze):
    mul = _main_statements(analyze, "           MULTIPLY 2 BY WS-A.\n")[0]
    assert isinstance(mul, MultiplyStatement)
    assert mul.multiply_type is MultiplyStatement.MultiplyType.BY
    assert isinstance(mul.operand_value_stmt, LiteralValueStmt)
    assert len(mul.by_targets) == 1
    assert mul.by_targets[0].call.name == "WS-A"


def test_multiply_by_giving_form(analyze):
    mul = _main_statements(analyze, "           MULTIPLY 2 BY WS-A GIVING WS-B ROUNDED.\n")[0]
    assert mul.multiply_type is MultiplyStatement.MultiplyType.BY_GIVING
    assert mul.giving_operand_value_stmt is not None
    assert mul.giving_operand_value_stmt.call.name == "WS-A"
    assert len(mul.giving_targets) == 1
    assert mul.giving_targets[0].call.name == "WS-B"
    assert mul.giving_targets[0].rounded is True


# --- DIVIDE ----------------------------------------------------------------

def test_divide_into_form(analyze):
    div = _main_statements(analyze, "           DIVIDE 2 INTO WS-A.\n")[0]
    assert isinstance(div, DivideStatement)
    assert div.divide_type is DivideStatement.DivideType.INTO
    assert isinstance(div.operand_value_stmt, LiteralValueStmt)
    assert len(div.into_targets) == 1
    assert div.into_targets[0].call.name == "WS-A"


def test_divide_into_giving_form(analyze):
    div = _main_statements(analyze, "           DIVIDE 2 INTO WS-A GIVING WS-B.\n")[0]
    assert div.divide_type is DivideStatement.DivideType.INTO_GIVING
    assert div.into_value_stmt is not None
    assert div.into_value_stmt.call.name == "WS-A"
    assert len(div.giving_targets) == 1
    assert div.giving_targets[0].call.name == "WS-B"


def test_divide_by_giving_remainder(analyze):
    div = _main_statements(
        analyze, "           DIVIDE 2 BY WS-A GIVING WS-B REMAINDER WS-R.\n"
    )[0]
    assert div.divide_type is DivideStatement.DivideType.BY_GIVING
    assert div.by_value_stmt is not None
    assert div.by_value_stmt.call.name == "WS-A"
    assert [g.call.name for g in div.giving_targets] == ["WS-B"]
    assert div.remainder_call is not None
    assert div.remainder_call.name == "WS-R"


# --- COMPUTE ---------------------------------------------------------------

def test_compute_store_and_expression(analyze):
    comp = _main_statements(analyze, "           COMPUTE WS-A = WS-B + 1.\n")[0]
    assert isinstance(comp, ComputeStatement)
    assert len(comp.stores) == 1
    assert comp.stores[0].call.name == "WS-A"
    assert comp.stores[0].rounded is False
    assert isinstance(comp.arithmetic_expression, ArithmeticValueStmt)


def test_compute_rounded_store(analyze):
    comp = _main_statements(analyze, "           COMPUTE WS-A ROUNDED = WS-B * 2.\n")[0]
    assert comp.stores[0].rounded is True


# --- shared ON SIZE ERROR phrase still owned -------------------------------

def test_arithmetic_on_size_error_phrase_owned(analyze):
    add = _main_statements(
        analyze,
        "           ADD 1 TO WS-A\n"
        "              ON SIZE ERROR\n"
        "                 MOVE 0 TO WS-A\n"
        "           END-ADD.\n",
    )[0]
    assert add.add_type is AddStatement.AddType.TO
    assert isinstance(add.on_size_error_phrase, OnSizeErrorPhrase)
    # the nested MOVE lives inside the SIZE ERROR phrase, not the paragraph
    assert len(add.on_size_error_phrase.statements) == 1
    assert isinstance(add.on_size_error_phrase.statements[0], MoveStatement)
