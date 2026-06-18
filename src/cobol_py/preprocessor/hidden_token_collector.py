"""Collects visible and hidden tokens of a parse subtree into a string.

Ports ``io.proleap.cobol.preprocessor.sub.document.impl.CobolHiddenTokenCollectorListenerImpl``.
"""

from __future__ import annotations

from cobol_py.CobolPreprocessorListener import CobolPreprocessorListener

from .token_utils import get_hidden_tokens_to_left, is_eof


class CobolHiddenTokenCollectorListenerImpl(CobolPreprocessorListener):
    """Walks a subtree appending hidden-tokens-to-the-left then each terminal."""

    def __init__(self, tokens) -> None:
        self._tokens = tokens
        self._output_buffer: list[str] = []
        self._first_terminal = True

    def read(self) -> str:
        return "".join(self._output_buffer)

    def visitTerminal(self, node) -> None:  # noqa: N802 - ANTLR callback name
        if not self._first_terminal:
            tok_pos = node.getSourceInterval()[0]
            self._output_buffer.append(
                get_hidden_tokens_to_left(tok_pos, self._tokens)
            )

        if not is_eof(node):
            self._output_buffer.append(node.getText())

        self._first_terminal = False
