"""Parse-tree golden comparison tests, mirroring proleap's
``io/proleap/cobol/ast`` JUnit tests.

Each ``.cbl`` under ``testdata/io/proleap/cobol/ast`` is parsed through the full
pipeline and its cleaned ``toStringTree`` output is compared to the committed
``.cbl.tree`` golden. This is the strongest fidelity check available: the Python
port must produce a parse tree identical to proleap's Java output, after the same
``CobolTestStringUtils.cleanFileTree`` whitespace normalisation proleap applies.

The source format is inferred from the golden's directory (``fixed`` / ``tandem``
/ ``variable``); copybooks resolve against the file's own directory, matching
proleap's ``createDefaultParams``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cobol_py import CobolParserRunner, CobolSourceFormatEnum
from cobol_py.params import CobolParserParams

AST_ROOT = (
    Path(__file__).resolve().parent
    / "testdata"
    / "io"
    / "proleap"
    / "cobol"
    / "ast"
)


def _clean_file_tree(value: str) -> str:
    """Port of ``io.proleap.cobol.util.CobolTestStringUtils.cleanFileTree``.

    Strips escaped/literal newlines and collapses all remaining whitespace
    (including the space before a closing paren) so the comparison ignores
    incidental whitespace differences between the Java and Python tree dumps.
    """
    value = value.replace("\\r", "").replace("\\n", "")
    value = value.replace("\r", "").replace("\n", "")
    value = re.sub(r"[\s]+", " ", value)
    value = re.sub(r"[\s]+\)", ")", value)
    return value


def _format_for(path: Path) -> CobolSourceFormatEnum:
    name = path.as_posix()
    if "/tandem/" in name:
        return CobolSourceFormatEnum.TANDEM
    if "/variable/" in name:
        return CobolSourceFormatEnum.VARIABLE
    return CobolSourceFormatEnum.FIXED


GOLDEN_PAIRS = sorted(p.with_suffix("") for p in AST_ROOT.rglob("*.cbl.tree"))


@pytest.mark.parametrize(
    "cbl", GOLDEN_PAIRS, ids=lambda p: p.relative_to(AST_ROOT).as_posix()
)
def test_parse_tree_matches_golden(cbl: Path):
    # Arrange
    params = CobolParserParams(
        format=_format_for(cbl), copy_book_directories=[cbl.parent]
    )

    # Act
    ast = CobolParserRunner().parse(cbl.read_text(encoding="utf-8"), params)

    # Assert - cleaned parse tree equals the committed golden.
    got = _clean_file_tree(ast.toStringTree(recog=ast.parser))
    golden_path = cbl.with_suffix(".cbl.tree")
    want = _clean_file_tree(golden_path.read_text(encoding="utf-8"))
    assert got == want, f"parse tree diverges from golden {golden_path.name}"
