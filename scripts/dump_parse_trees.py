#!/usr/bin/env python3
"""Dump cobol-py's normalized parse tree for every ``.cbl`` under a directory.

Mirrors the proleap Java ``io.proleap.cobol.ast.TreeDumper`` harness so the two
outputs can be diffed file-for-file, proving the Python port produces the same
parse trees as proleap over the shared ``ast/**`` golden set.

Run from the project root with the project environment active::

    uv run python scripts/dump_parse_trees.py <inputDir> <outputDir>

For each ``.cbl`` under ``<inputDir>`` (recursively), the cleaned
``toStringTree`` is written to ``<outputDir>/<relative-path>.tree`` — the same
layout and normalisation the Java dumper produces.
"""

from __future__ import annotations

import sys
from pathlib import Path

from cobol_py import CobolParserRunner
from cobol_py._treeutil import clean_file_tree, format_for
from cobol_py.params import CobolParserParams


def main(input_dir: Path, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(input_dir.rglob("*.cbl"))
    ok = 0
    for cbl in files:
        try:
            params = CobolParserParams(
                format=format_for(cbl), copy_book_directories=[cbl.parent]
            )
            ast = CobolParserRunner().parse(cbl.read_text(encoding="utf-8"), params)
            tree = clean_file_tree(ast.toStringTree(recog=ast.parser))
            out = output_dir / cbl.relative_to(input_dir)
            out = out.with_suffix(out.suffix + ".tree")  # name.cbl -> name.cbl.tree
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(tree, encoding="utf-8")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {cbl}: {exc}", file=sys.stderr)
    print(f"Dumped {ok}/{len(files)} trees to {output_dir}")
    return 0 if ok == len(files) else 1


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: dump_parse_trees.py <inputDir> <outputDir>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
