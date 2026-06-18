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

    # --- internal -----------------------------------------------------------

    def _parse_preprocess_input(
        self, pre_processed_input: str, params: CobolParserParams
    ):
        # run the lexer
        lexer = CobolLexer(InputStream(pre_processed_input))

        if not params.ignore_syntax_errors:
            lexer.removeErrorListeners()
            lexer.addErrorListener(ThrowingErrorListener())

        # get a list of matched tokens
        tokens = CommonTokenStream(lexer)

        # pass the tokens to the parser. The throwing error listener is attached
        # inside the two-stage parse (LL stage only) — see _start_rule_two_stage.
        parser = CobolParser(tokens)

        # specify our entry point -> the AST
        return self._start_rule_two_stage(parser, params.ignore_syntax_errors)

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
        """
        # Stage 1: fast SLL.
        parser.removeErrorListeners()
        parser._interp.predictionMode = PredictionMode.SLL
        parser._errHandler = BailErrorStrategy()
        try:
            return parser.startRule()
        except ParseCancellationException:
            pass

        # Stage 2: full LL.
        parser.getTokenStream().seek(0)
        parser.reset()
        parser._interp.predictionMode = PredictionMode.LL
        parser._errHandler = DefaultErrorStrategy()
        if not ignore_syntax_errors:
            parser.addErrorListener(ThrowingErrorListener())
        return parser.startRule()

