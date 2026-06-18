"""Helpers around ANTLR token streams and hidden tokens.

Ports ``io.proleap.cobol.preprocessor.sub.util.TokenUtils``.

Notes on the Python ANTLR4 runtime:

* ``TerminalNode.getSourceInterval()`` returns a ``(a, b)`` tuple (not an object
  with an ``.a`` attribute); ``[0]`` is the token index.
* ``Token`` objects use attribute access (``token.type``), not getters.
* The grammar's ``HIDDEN`` channel is the default hidden channel (== 1); we use
  ``Token.HIDDEN_CHANNEL`` to stay decoupled from the generated lexer.
"""

from __future__ import annotations

from antlr4 import Token
from antlr4.tree.Tree import ParseTreeWalker


def get_hidden_tokens_to_left(tok_pos, tokens) -> str:
    """Concatenate the text of all hidden-channel tokens to the left of *tok_pos*."""
    ref_channel = tokens.getHiddenTokensToLeft(tok_pos, Token.HIDDEN_CHANNEL)
    if not ref_channel:
        return ""
    # Python-runtime CommonToken exposes text via the ``.text`` attribute (no
    # getText()); guard against a None text (e.g. computed-later tokens).
    parts = []
    for t in ref_channel:
        text = t.text
        if text is not None:
            parts.append(text)
    return "".join(parts)


def is_eof(node) -> bool:
    return Token.EOF == node.getSymbol().type


def get_text_including_hidden_tokens(ctx, tokens) -> str:
    """Collect visible + hidden token text under *ctx* via a walk."""
    # Deferred import to avoid a token_utils <-> hidden_token_collector cycle.
    from .hidden_token_collector import CobolHiddenTokenCollectorListenerImpl

    listener = CobolHiddenTokenCollectorListenerImpl(tokens)
    ParseTreeWalker.DEFAULT.walk(listener, ctx)
    return listener.read()
