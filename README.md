# cobol-py

A **COBOL parser for Python** that ports the parsing pipeline of
[`proleap-cobol-parser`](https://github.com/uwol/proleap-cobol-parser) (Java) to
Python, built on [ANTLR4](https://www.antlr.org/).

`cobol-py` reproduces proleap's two-stage design:

1. **Preprocessor** (`CobolPreprocessor.g4`) — a fixed-format line model plus a
   document walker that expands `COPY` copybooks, applies `REPLACE` pseudo-text,
   and extracts `EXEC CICS` / `EXEC SQL` / `EXEC SQLIMS` blocks into tagged lines.
2. **Main grammar** (`Cobol.g4`) — parses the preprocessed text into a `startRule`
   AST.

> Scope is the **parsing pipeline** only (raw source → preprocessed text → AST).
> proleap's ASG layer (semantic analysis, data / control flow) is **not** ported.

## Install

```bash
uv sync                      # create .venv and install antlr4-python3-runtime + pytest
uv pip install -e .          # or, install the package into another project
```

Runtime dependency: [`antlr4-python3-runtime`](https://pypi.org/project/antlr4-python3-runtime/) `4.13.2`.

## Quick start

```python
from cobol_py import CobolParserRunner, CobolParserParams, CobolSourceFormatEnum

src = open("examples/example.cbl").read()

# A source format is required — it drives the fixed-format line model.
params = CobolParserParams(format=CobolSourceFormatEnum.FIXED)

ast = CobolParserRunner().parse(src, params)
print(ast.toStringTree(recog=ast.parser))   # noqa: the generated StartRuleContext
```

Or parse straight from a file (the file's directory becomes the default copybook
search path):

```python
from cobol_py import CobolParserRunner, CobolSourceFormatEnum

ast = CobolParserRunner().parse_file(
    "examples/example.cbl", CobolSourceFormatEnum.FIXED
)
```

## Source formats

COBOL source is column-oriented. `CobolSourceFormatEnum` selects the layout the
line reader expects:

| Format     | Sequence (cols) | Indicator | Area A  | Area B     |
|------------|-----------------|-----------|---------|------------|
| `FIXED`    | 1–6             | 7         | 8–12    | 13–72      |
| `VARIABLE` | 1–6             | 7         | 8–12    | 8–end      |
| `TANDEM`   | —               | 1         | 2–5     | 2–end      |

`FIXED` is the standard ANSI / IBM reference. Unlike `FIXED`, `VARIABLE` does
**not** drop a comment area past column 72, so long `AREA B` content survives
intact.

## Preprocessor constructs

`CobolPreprocessorImpl` performs the textual transforms that a pure grammar
cannot:

- **`COPY`** — inlines a copybook resolved against
  `params.copy_book_directories` / `copy_book_files` (by cobol-word, literal, or
  filename).
- **`REPLACE ==a== BY ==b==`** — applies pseudo-text replacement to the
  surrounding source.
- **`EXEC SQL|CICS|SQLIMS … END-EXEC`** — tags each line (`*>EXECSQL`, …) and
  emits a `}` terminator so the main grammar's lexer can recognise the block.

```python
from cobol_py import CobolPreprocessorImpl, CobolParserParams, CobolSourceFormatEnum

params = CobolParserParams(format=CobolSourceFormatEnum.FIXED)
preprocessed = CobolPreprocessorImpl().process(src, params)
```

## Walk the AST

The generated listener / visitor let you traverse the `startRule` tree:

```python
from cobol_py import CobolListener

class MyListener(CobolListener):
    def enterMoveStatement(self, ctx):        # noqa: N802
        print("found MOVE:", ctx.getText())
```

## Testing

```bash
uv run pytest                      # fast unit + AST golden tests (~130 tests)
COBOL_PY_NIST_FULL=1 uv run pytest tests/test_nist.py   # full NIST suite (slow)
```

| Module | What it checks |
|--------|----------------|
| `tests/test_phase1_leaf.py` | leaf types, params, format enum |
| `tests/test_phase2_line.py` | line sub-pipeline (reader / indicator / writer) |
| `tests/test_parse.py` | full pipeline on small FIXED/TANDEM/VARIABLE fixtures |
| `tests/test_ast_tree.py` | parse-tree **golden** comparison vs proleap's `.cbl.tree` files |
| `tests/test_nist.py` | NIST COBOL-85 conformance (a stride by default; full is opt-in) |

`tests/test_ast_tree.py` is the strongest fidelity check: it parses every program
under `testdata/io/proleap/cobol/ast` and asserts the cleaned `toStringTree` output
matches proleap's committed `.cbl.tree` golden byte-for-byte.

`tests/test_nist.py` mirrors proleap's `gov/nist/*Test.java` — it runs each NIST
program through `parse_file(file, FIXED)` and asserts a clean parse. The Python
ANTLR runtime simulates the ATN in pure Python, so prediction on this grammar is
~2-4 s per medium NIST file (vs. milliseconds on the JVM); the full 459-file
suite is therefore opt-in via `COBOL_PY_NIST_FULL=1`, while a representative
stride runs in the default suite.

## Regenerate the parser

The generated modules under `src/cobol_py/` are committed, but you can
regenerate them from `Cobol.g4` / `CobolPreprocessor.g4` after editing a grammar:

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
Cobol.g4                       # main COBOL grammar (source of truth)
CobolPreprocessor.g4           # preprocessor grammar (COPY/REPLACE/EXEC/opts)
pyproject.toml                 # uv / hatchling package definition
scripts/generate_parser.py     # regenerate src/cobol_py/*.py from the grammars
src/cobol_py/                  # importable package
  preprocessor/                # line reader/writer, indicator processor,
                               # comment marker, document parser, copybook finders
  runner.py                    # CobolParserRunner — the public entry point
  Cobol{Lexer,Parser,Listener,Visitor}.py
  CobolPreprocessor{Lexer,Parser,Listener,Visitor}.py
tests/
  fixtures/                    # .cbl/.CPY programs: FIXED/TANDEM/VARIABLE +
                               # COPY + REPLACE + EXEC SQL/CICS
  test_phase1_leaf.py          # leaf types & utils
  test_phase2_line.py          # line sub-pipeline
  test_parse.py                # full-pipeline integration tests
examples/example.cbl           # self-contained FIXED example
```

## Design notes & limitations

- The proleap whitespace model is preserved: `NEWLINE` and whitespace live on
  the HIDDEN channel and statements terminate on `DOT_FS`.
- `EXEC CICS/SQL/SQLIMS` bodies are parsed inline as a free-form token run up to
  `END-EXEC`, gated by the preprocessor-inserted `*>EXEC*` tags and the `}`
  terminator.
- `compilerOptions` is recognised tolerantly (the option stream is captured up to
  `IDENTIFICATION`).
- **Parse speed**: the runner uses ANTLR's SLL→LL two-stage strategy. SLL is
  exact and fast for most input; when it bails (ambiguity or a real syntax
  error), the runner falls back to full LL with the error listeners re-armed, so
  the parse tree and error behaviour are identical to a plain LL parse. This is a
  Python-specific optimisation — proleap on the JVM does not need it.
- The ASG / semantic-analysis layer of proleap is intentionally out of scope;
  the deliverable ends at the `startRule` AST.

## License

MIT.
