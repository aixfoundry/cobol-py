"""String helpers specific to the preprocessor.

Ports ``io.proleap.cobol.preprocessor.sub.util.PreprocessorStringUtils``.
"""

from __future__ import annotations

import re

_STRIP_QUOTES = re.compile(r"""^["']|["']$""")


def trim_quotes(text: str) -> str:
    """Strip a leading or trailing ``"`` / ``'`` from *text* (Java ``replaceAll``)."""
    return _STRIP_QUOTES.sub("", text)
