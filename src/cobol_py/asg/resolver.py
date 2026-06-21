"""Name resolver (ports ``asg/resolver/impl/NameResolverImpl``).

Dispatches on the runtime ctx type; cases that descend into a child are
explicit, everything else falls back to ``ctx.getText()``.
"""

from __future__ import annotations

from typing import Optional

from antlr4.ParserRuleContext import ParserRuleContext

from ..CobolParser import CobolParser


def _text(ctx) -> Optional[str]:
    return ctx.getText() if ctx is not None else None


def determine_name(ctx: Optional[ParserRuleContext]) -> Optional[str]:
    if ctx is None:
        return None
    CP = CobolParser

    if isinstance(ctx, CP.ProgramIdParagraphContext):
        return _text(ctx.programName())
    if isinstance(ctx, CP.ParagraphContext):
        return determine_name(ctx.paragraphName())
    if isinstance(ctx, CP.ProcedureSectionContext):
        header = ctx.procedureSectionHeader()
        return _text(header.sectionName()) if header is not None else ctx.getText()
    if isinstance(ctx, CP.DataDescriptionEntryFormat1Context):
        return _text(ctx.dataName())
    if isinstance(ctx, CP.DataDescriptionEntryFormat2Context):
        return _text(ctx.dataName())
    if isinstance(ctx, CP.DataDescriptionEntryFormat3Context):
        return _text(ctx.conditionName())
    if isinstance(ctx, CP.FileControlEntryContext):
        select = ctx.selectClause() if hasattr(ctx, "selectClause") else None
        if select is not None:
            file_name = select.fileName() if hasattr(select, "fileName") else None
            if file_name is not None:
                return file_name.getText()
        return ctx.getText()

    return ctx.getText()
