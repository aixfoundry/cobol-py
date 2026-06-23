"""Runs the full pipeline: preprocess -> main ``Cobol.g4`` parse -> AST.

Ports the parsing surface of
``io.proleap.cobol.asg.runner.impl.CobolParserRunnerImpl`` (the ASG analysis
layer - ``analyze*``, ``Program``, visitors - is out of scope; the deliverable
ends at the ``startRule`` AST, matching ``parsePreprocessInput``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

from antlr4 import CommonTokenStream, InputStream
from antlr4.atn.PredictionMode import PredictionMode
from antlr4.error.ErrorStrategy import BailErrorStrategy, DefaultErrorStrategy
from antlr4.error.Errors import ParseCancellationException

from .error_listener import ThrowingErrorListener
from .exceptions import CobolParserException
from .params import CobolParserParams
from .preprocessor.preprocessor import CobolPreprocessorImpl
from .CobolLexer import CobolLexer
from .CobolParser import CobolParser
from .preprocessor.constants import CobolSourceFormatEnum
from .util.string_utils import capitalize
from .util.filename_utils import remove_extension

_LOG = logging.getLogger(__name__)


class CobolParserRunner:
    """Preprocess COBOL source and parse it to a ``startRule`` AST."""

    # --- params -------------------------------------------------------------

    @staticmethod
    def _create_default_params(
        format: Optional[CobolSourceFormatEnum] = None,
        cobol_file: Optional[Union[str, Path]] = None,
    ) -> CobolParserParams:
        result = CobolParserParams()
        if format is not None:
            result.format = format
        if cobol_file is not None:
            copy_books_directory = Path(cobol_file).parent
            result.copy_book_directories = [copy_books_directory]
        return result

    @staticmethod
    def _get_compilation_unit_name(cobol_file: Union[str, Path]) -> str:
        return capitalize(remove_extension(Path(cobol_file).name))

    # --- public API ---------------------------------------------------------

    def parse(
        self,
        cobol_code: str,
        params: Optional[CobolParserParams] = None,
    ):
        if params is None:
            params = self._create_default_params()
        _LOG.info("Parsing compilation unit.")
        pre_processed_input = CobolPreprocessorImpl().process(cobol_code, params)
        return self._parse_preprocess_input(pre_processed_input, params)

    def parse_file(
        self,
        cobol_file: Union[str, Path],
        format: Optional[CobolSourceFormatEnum] = None,
    ):
        if not Path(cobol_file).is_file():
            raise CobolParserException("Could not find file " + str(Path(cobol_file).resolve()))

        compilation_unit_name = self._get_compilation_unit_name(cobol_file)
        _LOG.info("Parsing compilation unit %s.", compilation_unit_name)

        if format is not None:
            params = self._create_default_params(format, cobol_file)
        else:
            params = self._create_default_params()

        pre_processed_input = CobolPreprocessorImpl().process_file(cobol_file, params)
        return self._parse_preprocess_input(pre_processed_input, params)

    # --- ASG analysis -------------------------------------------------------

    def analyze(
        self,
        cobol_code: str,
        params: Optional[CobolParserParams] = None,
        compilation_unit_name: Optional[str] = None,
    ):
        """Preprocess, parse to an AST, then build the ASG :class:`Program`.

        Ports ``CobolParserRunnerImpl.analyzeCode``. The deliverable of
        ``parse``/``parse_file`` is the ``startRule`` AST; this method runs the
        additional ASG visitor passes (porting ``analyze()``) and returns the
        semantic ``Program`` model.
        """
        from .asg.program import Program
        from .asg.visitor import CobolCompilationUnitVisitor, CobolProgramUnitVisitor

        if params is None:
            params = self._create_default_params()

        name = compilation_unit_name or "Anonymous"
        _LOG.info("Analyzing compilation unit %s.", name)

        pre_processed_input = CobolPreprocessorImpl().process(cobol_code, params)
        ctx, tokens = self._lex_and_parse(pre_processed_input, params)

        program = Program()
        lines = pre_processed_input.splitlines()
        CobolCompilationUnitVisitor(name, lines, tokens, program).visit(ctx)

        # Phase A wires only the program-unit pass; data/procedure-statement
        # passes are added in later phases via _run_analysis_passes.
        self._run_analysis_passes(program)
        return program

    def analyze_file(
        self,
        cobol_file: Union[str, Path],
        format: Optional[CobolSourceFormatEnum] = None,
    ):
        """Analyze a COBOL file into an ASG :class:`Program`."""
        if not Path(cobol_file).is_file():
            raise CobolParserException("Could not find file " + str(Path(cobol_file).resolve()))

        compilation_unit_name = self._get_compilation_unit_name(cobol_file)
        if format is not None:
            params = self._create_default_params(format, cobol_file)
        else:
            params = self._create_default_params()

        with open(cobol_file, "r", encoding=params.charset) as fh:
            cobol_code = fh.read()

        return self.analyze(cobol_code, params, compilation_unit_name)

    @staticmethod
    def _run_analysis_passes(program) -> None:
        """Run the ASG build passes that are currently implemented.

        Mirrors ``CobolParserRunnerImpl.analyze(program)``. Each phase extends
        this: Phase A = program units (run during the compilation-unit visit);
        Phase B adds the procedure-division pass; Phase C1 the statement pass;
        Phases D/E the data/environment passes.
        """
        from .asg.visitor import (
            CobolDataDivisionVisitor,
            CobolProcedureDivisionVisitor,
            CobolProcedureStatementVisitor,
            CobolProgramUnitVisitor,
        )

        # Pass 1: program units + the four divisions (must precede pass 2, so
        # that ProcedureDivision/DataDivision are registered before located).
        for compilation_unit in program.compilation_units:
            CobolProgramUnitVisitor(compilation_unit).visit(compilation_unit.ctx)

        # Pass 2: data-division sections + data-description hierarchy. Must
        # precede the statement pass so data references can resolve to entries.
        for compilation_unit in program.compilation_units:
            CobolDataDivisionVisitor(program).visit(compilation_unit.ctx)

        # Pass 3: procedure-division structure (sections, paragraphs, clauses).
        # Must precede pass 4 so PERFORM/GOTO calls can resolve to paragraphs.
        for compilation_unit in program.compilation_units:
            CobolProcedureDivisionVisitor(program).visit(compilation_unit.ctx)

        # Pass 3: typed procedure statements (Phase C1 core verbs).
        for compilation_unit in program.compilation_units:
            CobolProcedureStatementVisitor(program).visit(compilation_unit.ctx)

    # --- internal -----------------------------------------------------------

    def _lex_and_parse(
        self, pre_processed_input: str, params: CobolParserParams
    ):
        """Lex and parse preprocessed input, returning ``(ctx, tokens)``."""
        lexer = CobolLexer(InputStream(pre_processed_input))

        if not params.ignore_syntax_errors:
            lexer.removeErrorListeners()
            lexer.addErrorListener(ThrowingErrorListener())

        tokens = CommonTokenStream(lexer)
        parser = CobolParser(tokens)
        ctx = self._start_rule_two_stage(parser, params.ignore_syntax_errors)
        return ctx, tokens

    def _parse_preprocess_input(
        self, pre_processed_input: str, params: CobolParserParams
    ):
        return self._lex_and_parse(pre_processed_input, params)[0]

    @staticmethod
    def _start_rule_two_stage(parser, ignore_syntax_errors: bool):
        """Parse with the ANTLR SLL -> LL two-stage strategy.

        Stage 1 runs SLL prediction with a bail strategy and **no** error
        listeners attached: SLL is approximate and can flag false-positive
        errors on this large, ambiguous grammar, so a throwing listener here
        would raise on those and defeat the LL fallback. If SLL bails (a real
        syntax error or a false positive), stage 2 rewinds and re-parses with
        full LL, re-arming the error listeners so genuine syntax errors are
        reported exactly as a plain LL parse would. The parse tree is identical
        to a plain LL parse.

        A recursion-depth cap is applied to the ATN closure computation to
        prevent stack overflow on deeply-nested qualified data names (see
        :mod:`._antlr_patch`).
        """
        from ._antlr_patch import patch_context

        # Stage 1: fast SLL.
        parser.removeErrorListeners()
        parser._interp.predictionMode = PredictionMode.SLL
        parser._errHandler = BailErrorStrategy()
        try:
            return parser.startRule()
        except ParseCancellationException:
            pass

        # Stage 2: full LL, with ATN closure depth protection.
        parser.getTokenStream().seek(0)
        parser.reset()
        parser._interp.predictionMode = PredictionMode.LL
        parser._errHandler = DefaultErrorStrategy()
        if not ignore_syntax_errors:
            parser.addErrorListener(ThrowingErrorListener())
        with patch_context():
            return parser.startRule()

