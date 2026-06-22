"""A replaceable -> replacement mapping for the REPLACE statement.

Ports ``io.proleap.cobol.preprocessor.sub.document.impl.CobolReplacementMapping``.

Whitespace in a COBOL replaceable matches line breaks, so the replaceable
search string is turned into a regex whose words are joined by ``[\\r\\n\\s]+``
and each word is ``re.escape``-d (Java ``Pattern.quote``). Replacements are
applied longest-replaceable-first (see :meth:`CobolDocumentContext.replace_replaceables_by_replacements`).
"""

from __future__ import annotations

import re

from .token_utils import get_text_including_hidden_tokens

_PSEUDO_LEADING_EQ = re.compile(r"^==")
_PSEUDO_TRAILING_EQ = re.compile(r"==$")
_WS_SPLIT = re.compile(r"\s+")
_REGEX_SEPARATOR = r"[\r\n\s]+"


def _quote_replacement(replacement: str) -> str:
    """Java ``Matcher.quoteReplacement``: escape backslashes (Python re.sub has
    no ``$`` interpolation, so only ``\\`` needs escaping)."""
    return replacement.replace("\\", "\\\\")


class CobolReplacementMapping:
    """One ``replaceable -> replacement`` pair.

    ``replaceable`` / ``replacement`` hold the ANTLR rule contexts
    (``ReplaceableContext`` / ``ReplacementContext``) assigned by the document
    context; their text is resolved lazily at :meth:`replace` time.
    """

    def __init__(self) -> None:
        self.replaceable = None
        self.replacement = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CobolReplacementMapping):
            return NotImplemented
        return (
            self.replaceable.getText() == other.replaceable.getText()
            and self.replacement.getText() == other.replacement.getText()
        )

    def __lt__(self, other: "CobolReplacementMapping") -> bool:
        # Java compareTo(o) = o.replaceable.len - self.replaceable.len, i.e. the
        # longer replaceable sorts first. sorted() ascending with this __lt__
        # reproduces Arrays.sort (longest replaceable first).
        return len(self.replaceable.getText()) > len(other.replaceable.getText())

    def __hash__(self) -> int:  # pragma: no cover - parity with __eq__
        return hash((self.replaceable.getText(), self.replacement.getText()))

    def __repr__(self) -> str:  # noqa: D401
        return f"{self.replaceable.getText()} -> {self.replacement.getText()}"

    # --- replacement logic --------------------------------------------------

    def _extract_pseudo_text(self, pseudo_text_ctx, tokens) -> str:
        pseudo_text = get_text_including_hidden_tokens(pseudo_text_ctx, tokens).strip()
        content = _PSEUDO_LEADING_EQ.sub("", pseudo_text)
        content = _PSEUDO_TRAILING_EQ.sub("", content)
        return content.strip()

    def _get_regex_from_replaceable(self, replaceable):
        if replaceable is None:
            return None
        parts = _WS_SPLIT.split(replaceable)
        # Java's String.split(regex) (limit 0) discards trailing empty strings;
        # Python's re.split keeps them, which would append a trailing separator
        # to the joined regex and break matching when the replaceable carries
        # trailing hidden whitespace. Trim trailing empties to match Java.
        while parts and parts[-1] == "":
            parts.pop()
        regex_parts = [re.escape(part) for part in parts]
        return _REGEX_SEPARATOR.join(regex_parts)

    def _get_text(self, ctx, tokens):
        if ctx.pseudoText() is not None:
            return self._extract_pseudo_text(ctx.pseudoText(), tokens)
        if ctx.charDataLine() is not None:
            return get_text_including_hidden_tokens(ctx, tokens)
        if ctx.cobolWord() is not None:
            return ctx.getText()
        if ctx.literal() is not None:
            return ctx.literal().getText()
        return None

    def replace(self, string: str, tokens) -> str:
        replaceable_string = self._get_text(self.replaceable, tokens)
        replacement_string = self._get_text(self.replacement, tokens)

        if replaceable_string is not None and replacement_string is not None:
            replaceable_regex = self._get_regex_from_replaceable(replaceable_string)
            quoted_replacement = _quote_replacement(replacement_string)
            return re.compile(replaceable_regex).sub(quoted_replacement, string)
        return string
