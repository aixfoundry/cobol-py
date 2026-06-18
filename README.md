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
- The ASG / semantic-analysis layer of proleap is intentionally out of scope;
  the deliverable ends at the `startRule` AST.

## License

MIT.
