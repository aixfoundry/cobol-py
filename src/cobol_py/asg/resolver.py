"""Name resolver.

Ports ``asg/resolver/impl/NameResolverImpl``. The Java resolver is a set of
``determineName(XxxContext)`` overloads; Python cannot overload by static type,
so :func:`determine_name` dispatches on the runtime ctx type. The cases that
need to descend into a child (paragraph -> paragraphName, section -> section
name, program-id -> programName) are handled explicitly; everything else falls
back to ``ctx.getText()``.
"""

from __future__ import annotations

from typing import Optional

from antlr4.ParserRuleContext import ParserRuleContext

from ..CobolParser import CobolParser


def _text(ctx) -> Optional[str]:
    return ctx.getText() if ctx is not None else None


def determine_name(ctx: Optional[ParserRuleContext]) -> Optional[str]:
    """Return a display name for ``ctx`` (None if ``ctx`` is None)."""
    if ctx is None:
        return None

    CP = CobolParser

    if isinstance(ctx, CP.ProgramIdParagraphContext):
        return _text(ctx.programName())
    if isinstance(ctx, CP.ParagraphContext):
        return determine_name(ctx.paragraphName())
    if isinstance(ctx, CP.ProcedureSectionContext):
        header = ctx.procedureSectionHeader()
        if header is not None:
            return _text(header.sectionName())
        return ctx.getText()

    # ParagraphNameContext, SectionNameContext, ProgramNameContext, DataNameContext,
    # CobolWordContext and all other name-like contexts: their text IS the name.
    return ctx.getText()
