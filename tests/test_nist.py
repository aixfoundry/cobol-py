"""NIST COBOL-85 conformance tests, mirroring cobol-go's ``test/nist_test.go``.

Each test parses one program from the NIST suite (``testdata/gov/nist``) through the
full pipeline — preprocessor + ``Cobol.g4`` — and:

1. Caches the preprocessed output as ``{filename}.preprocessed`` (like Go)
2. Writes the ANTLR ``Trees.toStringTree`` output as ``{filename}.tree`` (like Go)
3. Writes collected syntax errors as ``{filename}.errors``, one per line, only when
   errors exist (no file = clean parse)
4. Uses the runner's optimized SLL→LL two-stage parse with raised recursion limit

By default a representative stride of programs runs as a fast smoke test.
Set ``COBOL_PY_NIST_FULL=1`` to parse all 459 files.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from cobol_py._treeutil import format_tree
from cobol_py.CobolLexer import CobolLexer
from cobol_py.CobolParser import CobolParser
from cobol_py.params import CobolParserParams
from cobol_py.preprocessor.constants import detect_source_format
from cobol_py.preprocessor.preprocessor import CobolPreprocessorImpl

NIST_DIR = Path(__file__).resolve().parent / "testdata" / "gov" / "nist"
ALL_NIST = sorted(NIST_DIR.glob("*.CBL"))

_SUBSET_STRIDE = 15
# The ANTLR Python runtime's PredictionContext.merge() recurses deeply for
# NC207A (28 s) and NC246A (~349 s).  runner._ensure_recursion_limit() raises
# sys.setrecursionlimit to 10 000 so these parse correctly, albeit slowly.
_SKIP_FILES: frozenset[str] = frozenset()


class _CollectingErrorListener(ErrorListener):
    """Collect syntax errors — mirrors Go's ``ErrorListener``."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append(f"line {line}:{column} {msg}")


def _preprocess(cbl: Path) -> str:
    """Preprocess *cbl*, using ``.preprocessed`` cache like Go."""
    cache_path = Path(str(cbl) + ".preprocessed")
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    raw = cbl.read_text(encoding="latin-1")
    fmt = detect_source_format(raw.splitlines()[:50])
    params = CobolParserParams(
        format=fmt,
        charset="latin-1",
        ignore_missing_copy=True,
        copy_book_directories=[cbl.parent],
        copy_book_extensions=["CPY", "cpy"],
    )
    processed = CobolPreprocessorImpl().process(raw, params)
    cache_path.write_text(processed, encoding="utf-8")
    return processed


# ---------------------------------------------------------------------------
# parametrisation
# ---------------------------------------------------------------------------

def _nist_files() -> list[Path]:
    if os.environ.get("COBOL_PY_NIST_FULL"):
        files = [p for p in ALL_NIST if p.stem not in _SKIP_FILES]
        # --resume: skip files that already have a .tree
        return [p for p in files if not p.with_suffix(".CBL.tree").exists()]
    return ALL_NIST[::_SUBSET_STRIDE]


def _nist_params() -> list:
    return [pytest.param(cbl) for cbl in _nist_files()]


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cbl", _nist_params(), ids=lambda p: p.stem)
def test_nist_program_parses(cbl: Path):
    """Parse each NIST program, cache .preprocessed / .tree / .errors files."""
    # Preprocess (cached like Go)
    processed = _preprocess(cbl)

    # Lex + parse collected syntax errors (like Go's ErrorListener).
    from cobol_py._antlr_patch import patch_context
    from cobol_py.runner import _ensure_recursion_limit

    _ensure_recursion_limit()

    lexer = CobolLexer(InputStream(processed))
    tokens = CommonTokenStream(lexer)
    parser = CobolParser(tokens)
    err_listener = _CollectingErrorListener()
    parser.addErrorListener(err_listener)
    with patch_context():
        tree = parser.startRule()

    # Always write .tree file (like Go)
    tree_str = format_tree(tree, parser)
    tree_path = Path(str(cbl) + ".tree")
    tree_path.write_text(tree_str, encoding="utf-8")

    # Write .errors file only when errors exist (one per line)
    errors_path = Path(str(cbl) + ".errors")
    if err_listener.errors:
        errors_path.write_text("\n".join(err_listener.errors) + "\n", encoding="utf-8")
    else:
        errors_path.unlink(missing_ok=True)

    # Fail the test if any errors were collected
    for err in err_listener.errors:
        pytest.fail(err)
