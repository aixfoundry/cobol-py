#!/usr/bin/env python3
"""Regenerate the Cobol85 ANTLR4 Python parser from ``Cobol85.g4``.

Run from the project root with the project environment active::

    uv run python scripts/generate_parser.py

The generator is the official ANTLR4 jar (``antlr-<ver>-complete.jar``), driven
through ``java``. The jar version is derived from the installed
``antlr4-python3-runtime`` so the emitted ATN and the runtime always agree; if
the jar is missing it is downloaded from www.antlr.org. A JDK must be on PATH.

Output is written into ``src/cobol_py/`` and only the importable ``*.py`` modules
are kept (``.interp`` / ``.tokens`` build artifacts are removed).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAMMAR = ROOT / "Cobol85.g4"
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
    if not GRAMMAR.is_file():
        print(f"error: grammar not found: {GRAMMAR}", file=sys.stderr)
        return 1
    version = runtime_version()
    jar = ensure_jar(version)
    PKG.mkdir(parents=True, exist_ok=True)

    # Run from ROOT with a *relative* grammar path so ANTLR writes directly into
    # the -o dir instead of mirroring an absolute path under it.
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
        "Cobol85.g4",
    ]
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

    # Drop non-importable build artifacts; the Python runtime embeds the ATN.
    for pattern in ("*.interp", "*.tokens"):
        for artifact in PKG.glob(pattern):
            artifact.unlink()

    generated = sorted(p.name for p in PKG.glob("Cobol85*.py"))
    print(
        f"generated {len(generated)} module(s) (ANTLR {version}) "
        f"into {PKG.relative_to(ROOT)}:"
    )
    for name in generated:
        print(f"  - {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
