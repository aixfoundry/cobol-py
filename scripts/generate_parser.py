#!/usr/bin/env python3
"""Regenerate the ANTLR4 Python parser from the two COBOL grammars.

Run from the project root with the project environment active::

    uv run python scripts/generate_parser.py

Generates the lexer / parser / listener / visitor for **both** grammars, matching
proleap's two-stage design:

* ``Cobol.g4``            -> ``Cobol{Lexer,Parser,Listener,Visitor}.py``
* ``CobolPreprocessor.g4``-> ``CobolPreprocessor{Lexer,Parser,Listener,Visitor}.py``

The generator is the official ANTLR4 jar (``antlr-<ver>-complete.jar``), driven through
``java``. The jar version is derived from the installed ``antlr4-python3-runtime`` so the
emitted ATN and the runtime always agree; if the jar is missing it is downloaded from
www.antlr.org. A JDK must be on PATH.

Output is written into ``src/cobol_py/`` and only the importable ``*.py`` modules are kept
(``.interp`` / ``.tokens`` build artifacts are removed).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# proleap's two-grammar design: a preprocessor pass, then the main COBOL grammar.
GRAMMARS = ("Cobol.g4", "CobolPreprocessor.g4")
# Names of generated parser roots, used for reporting and stale-file cleanup.
PARSER_ROOTS = ("Cobol", "CobolPreprocessor")
PKG = ROOT / "src" / "cobol_py"
TOOLS = ROOT / ".tools"
ANTLR_BASE_URL = "https://www.antlr.org/download"


def runtime_version() -> str:
    try:
        from importlib.metadata import version

        return version("antlr4-python3-runtime")
    except Exception as exc:  # pragma: no cover - environment error
        sys.exit(
            "error: cannot determine antlr4-python3-runtime version "
            f"(is the project installed?): {exc}"
        )


def ensure_jar(version: str) -> Path:
    jar = TOOLS / f"antlr-{version}-complete.jar"
    if jar.is_file():
        return jar
    TOOLS.mkdir(parents=True, exist_ok=True)
    url = f"{ANTLR_BASE_URL}/antlr-{version}-complete.jar"
    print(f"downloading {url}")
    with urllib.request.urlopen(url) as resp, open(jar, "wb") as fh:  # noqa: S310
        shutil.copyfileobj(resp, fh)
    return jar


def main() -> int:
    missing = [g for g in GRAMMARS if not (ROOT / g).is_file()]
    if missing:
        print(f"error: grammar(s) not found: {', '.join(missing)}", file=sys.stderr)
        return 1

    version = runtime_version()
    jar = ensure_jar(version)
    PKG.mkdir(parents=True, exist_ok=True)

    # Run ANTLR once over both grammars. They are independent (no token-vocab
    # dependency), so a single invocation emits all eight modules. Relative grammar
    # paths with cwd=ROOT make ANTLR write straight into -o instead of mirroring an
    # absolute path under it. -lib ROOT lets the grammars resolve any sibling files.
    cmd = [
        "java",
        "-jar",
        str(jar),
        "-Dlanguage=Python3",
        "-visitor",
        "-listener",
        "-lib",
        str(ROOT),
        "-o",
        str(PKG),
        *GRAMMARS,
    ]
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

    # Drop non-importable build artifacts; the Python runtime embeds the ATN.
    for pattern in ("*.interp", "*.tokens"):
        for artifact in PKG.glob(pattern):
            artifact.unlink()

    # Remove any stale parser modules from the old single-grammar design so they cannot
    # shadow the new ones (e.g. Cobol85Lexer.py from the deleted Cobol85.g4).
    stale_roots = {"Cobol85"}
    for stale in stale_roots:
        for artifact in PKG.glob(f"{stale}*.py"):
            print(f"removing stale generated module: {artifact.name}")
            artifact.unlink()

    # Dedup: the "Cobol*.py" glob also matches "CobolPreprocessor*.py", so build the
    # report from a set. Each grammar yields {Lexer,Parser,Listener,Visitor}.py.
    generated = sorted(
        {p.name for root in PARSER_ROOTS for p in PKG.glob(f"{root}*.py")}
    )
    print(
        f"generated {len(generated)} module(s) (ANTLR {version}) "
        f"into {PKG.relative_to(ROOT)}:"
    )
    for name in generated:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
