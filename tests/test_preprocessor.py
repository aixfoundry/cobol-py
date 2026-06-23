"""Preprocessor golden comparison tests, mirroring proleap's
``io/proleap/cobol/preprocessor`` JUnit tests.

Each ``.cbl`` under ``testdata/io/proleap/cobol/preprocessor`` is preprocessed
through ``CobolPreprocessorImpl``; the resulting text is compared to the
committed ``.cbl.preprocessed`` golden, then written back to the same file
so ``git diff`` reveals any divergence.

The source format is inferred from the directory (see ``format_for``);
copybook directories are discovered from ``copybooks/`` subdirs when present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cobol_py._treeutil import format_for
from cobol_py.params import CobolParserParams
from cobol_py.preprocessor.preprocessor import CobolPreprocessorImpl

PREPROCESSOR_ROOT = (
    Path(__file__).resolve().parent
    / "testdata"
    / "io"
    / "proleap"
    / "cobol"
    / "preprocessor"
)

# Known-ignored in Java (CopyOfTest) or pre-existing preprocessor limitations.
_XFAIL_PREPROCESS = {
    "copy/copyof/CopyOf.cbl",  # COPY … OF "=lib" syntax — @Ignore in Java
}


def _find_golden_pairs() -> list[tuple[Path, bool]]:
    """Return ``(cbl, xfail)`` for files that have a ``.cbl.preprocessed`` golden."""
    pairs: list[tuple[Path, bool]] = []
    for golden in sorted(PREPROCESSOR_ROOT.rglob("*.cbl.preprocessed")):
        cbl = golden.with_suffix("")  # .cbl.preprocessed → .cbl
        if not cbl.is_file():
            continue
        rel = str(cbl.relative_to(PREPROCESSOR_ROOT).as_posix())
        pairs.append((cbl, rel in _XFAIL_PREPROCESS))
    return pairs


GOLDEN_PAIRS = _find_golden_pairs()
GOLDEN_IDS = [
    str(cbl.relative_to(PREPROCESSOR_ROOT).as_posix()) for cbl, _xfail in GOLDEN_PAIRS
]


def _copy_book_dirs(cbl: Path) -> list[Path]:
    """Discover copybook directories relative to the CBL file."""
    dirs: list[Path] = []
    candidate = cbl.parent / "copybooks"
    if candidate.is_dir():
        dirs.append(candidate)
    dirs.append(cbl.parent)
    return dirs


@pytest.mark.parametrize(
    "cbl, xfail", GOLDEN_PAIRS, ids=GOLDEN_IDS,
)
def test_preprocessor_matches_golden(cbl: Path, xfail: bool):
    # Arrange
    fmt = format_for(cbl)
    copy_dirs = _copy_book_dirs(cbl)
    params = CobolParserParams(format=fmt, copy_book_directories=copy_dirs)
    code = cbl.read_text(encoding="utf-8")

    # Act — preprocess (may xfail for known-unresolved copybooks).
    if xfail:
        with pytest.raises(Exception):
            CobolPreprocessorImpl().process(code, params)
        return

    preprocessed = CobolPreprocessorImpl().process(code, params)

    # Assert — preprocessed text equals committed golden.
    golden_path = cbl.with_suffix(cbl.suffix + ".preprocessed")
    want = golden_path.read_text(encoding="utf-8")
    assert preprocessed == want, f"preprocessor output diverges from golden {golden_path.name}"

    # Overwrite golden so git diff reveals any divergence.
    golden_path.write_text(preprocessed, encoding="utf-8")
