# cobol-py

A single-pass **COBOL 85 parser for Python**, built on a merged [ANTLR4](https://www.antlr.org/) grammar.

`cobol-py` merges the former two-stage design of `grammars-v4/cobol85` (a
`Cobol85Preprocessor.g4` pass followed by a `Cobol85.g4` pass) into **one
grammar** that parses a raw COBOL source file into a complete AST in a single
pass. The preprocessor constructs — compiler options (`PROCESS`/`CBL`), `COPY`,
`REPLACE`, `EXEC CICS` / `EXEC SQL` / `EXEC SQLIMS`, and the `EJECT` / `SKIP` /
`TITLE` directives — are recognised as AST nodes rather than executed.

> A pure grammar cannot perform the file I/O of `COPY` or the token rewriting of
> `REPLACE`, so `cobol-py` **recognises** these constructs. A downstream walker
> can traverse the tree and expand copybooks / apply replacements if needed.

## Install

```bash
uv sync                      # create .venv and install antlr4-python3-runtime + pytest
uv pip install -e .          # or, install the package into another project
```

Runtime dependency: [`antlr4-python3-runtime`](https://pypi.org/project/antlr4-python3-runtime/) `4.13.2`.

## Quick start

```python
from antlr4 import CommonTokenStream, InputStream
from cobol_py import Cobol85Lexer, Cobol85Parser

src = open("examples/example_merged.cbl").read()
lexer = Cobol85Lexer(InputStream(src))
parser = Cobol85Parser(CommonTokenStream(lexer))
tree = parser.startRule()
print(tree.toStringTree(recog=parser))
```

Walk the tree with a listener (override only the rules you care about):

```python
from cobol_py import Cobol85Listener

class MyListener(Cobol85Listener):
    def enterCopyStatement(self, ctx):
        print("found COPY:", ctx.getText())
```

## Regenerate the parser

The generated modules under `src/cobol_py/` are committed, but you can
regenerate them from `Cobol85.g4` after editing the grammar:

```bash
uv run python scripts/generate_parser.py
uv run pytest                 # verify
```

The generator drives the official ANTLR4 jar through `java`. The jar version is
derived from the installed `antlr4-python3-runtime` (so the emitted ATN and the
runtime always agree); the jar is cached under `.tools/` and downloaded
automatically if missing. A JDK must be on `PATH`.

## Project layout

```
Cobol85.g4                  # merged grammar (source of truth)
pyproject.toml              # uv / hatchling package definition
scripts/generate_parser.py  # regenerate src/cobol_py/*.py from the grammar
src/cobol_py/               # importable package (generated parser + exports)
  __init__.py
  Cobol85Lexer.py
  Cobol85Parser.py
  Cobol85Listener.py
  Cobol85Visitor.py
tests/test_parse.py         # round-trip parse tests
examples/example_merged.cbl # exercises all merged constructs in one pass
```

## Design notes & limitations

- The COBOL 85 whitespace model of the original grammar is preserved: `NEWLINE`
  and whitespace live on the HIDDEN channel and statements terminate on `DOT_FS`.
- `EXEC CICS/SQL/SQLIMS` bodies are parsed inline as a free-form token run up to
  `END-EXEC` (`~END_EXEC*`); they no longer rely on preprocessor-inserted marker
  tokens (`*>EXECCICS`, …).
- `compilerOptions` is recognised tolerantly (the option stream is captured as
  words/literals/punctuation up to `IDENTIFICATION`). Enumerating all ~170
  option abbreviations would force single-letter tokens into the lexer and steal
  them from `IDENTIFIER`.
- `commentEntry` is bounded by excluding the next paragraph/division header; a
  comment entry that happens to contain one of those exact words (`DATA`,
  `PROCEDURE`, …) will delimit early.
- Fixed-format column-7 indicators (`*` comment, `-` continuation, `/` page
  eject) are a preprocessing concern and are not handled by the grammar alone.
- `EXEC`, `CICS`, `SQL`, `SQLIMS`, … are reserved words in the merged grammar.

## License

MIT.
