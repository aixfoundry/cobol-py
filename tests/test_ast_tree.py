"""Parse-tree golden comparison tests, mirroring proleap's
``io/proleap/cobol/ast`` JUnit tests.

Each ``.cbl`` under ``testdata/io/proleap/cobol/ast`` is parsed through the full
pipeline and its ``toStringTree`` output is compared to the committed
``.cbl.tree`` golden (whitespace-normalised via ``clean_file_tree``).
The golden is overwritten with ``format_tree`` output — the multi-line,
tab-indented ANTLR ``Trees.toStringTree`` format matching Java — so
``git diff`` reveals any divergence against the Java reference.

The source format is inferred from the golden's directory (``fixed`` / ``tandem``
/ ``variable``); copybooks resolve against the file's own directory, matching
proleap's ``createDefaultParams``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cobol_py import CobolParserRunner
from cobol_py._treeutil import clean_file_tree, format_for, format_tree
from cobol_py.params import CobolParserParams

AST_ROOT = (
    Path(__file__).resolve().parent
    / "testdata"
    / "io"
    / "proleap"
    / "cobol"
    / "ast"
)


GOLDEN_PAIRS = sorted(p.with_suffix("") for p in AST_ROOT.rglob("*.cbl.tree"))


@pytest.mark.parametrize(
    "cbl", GOLDEN_PAIRS, ids=lambda p: p.relative_to(AST_ROOT).as_posix()
)
def test_parse_tree_matches_golden(cbl: Path):
    # Arrange
    params = CobolParserParams(
        format=format_for(cbl), copy_book_directories=[cbl.parent]
    )

    # Act
    ast = CobolParserRunner().parse(cbl.read_text(encoding="utf-8"), params)
    tree_text = ast.toStringTree(recog=ast.parser)

    # Assert - cleaned parse tree equals the committed golden.
    golden_path = cbl.with_suffix(".cbl.tree")
    want = clean_file_tree(golden_path.read_text(encoding="utf-8"))
    got = clean_file_tree(tree_text)
    assert got == want, f"parse tree diverges from golden {golden_path.name}"

    # Overwrite golden with Java-style multi-line tab-indented tree so
    # git diff shows any divergence against the Java reference output.
    golden_path.write_text(format_tree(ast, ast.parser), encoding="utf-8")
