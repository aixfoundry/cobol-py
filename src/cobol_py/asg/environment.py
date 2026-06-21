"""Environment division metamodel (Phase E).

Ports ``metamodel/environment``. The high-value piece for reference resolution is
the **file-control** chain: EnvironmentDivision → InputOutputSection →
FileControlParagraph → FileControlEntry (a ``SELECT``), so file-name references
resolve to :class:`FileControlEntryCall`. Configuration / special-names /
I-O-control are captured as minimal stubs (ctx retained); their clause detail is
deferred.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from antlr4.ParserRuleContext import ParserRuleContext

from .base import CobolDivisionElement, NamedElement

if TYPE_CHECKING:
    from .data import FileDescriptionEntry
    from .program import ProgramUnit


def _symbol(name: Optional[str]) -> Optional[str]:
    if name is None or name == "":
        return name
    return name.upper()


class ConfigurationSection(CobolDivisionElement):
    """CONFIGURATION SECTION. Source/object-computer paragraphs: deferred."""


class SpecialNamesParagraph(CobolDivisionElement):
    """SPECIAL-NAMES paragraph. Clause detail deferred."""


class IoControlParagraph(CobolDivisionElement):
    """I-O-CONTROL paragraph. Deferred."""


class FileControlEntry(CobolDivisionElement, NamedElement):
    """One ``SELECT`` statement: a file-name + its clauses."""

    def __init__(self, name, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name
        self.assign: Optional[str] = None
        self.organization: Optional[str] = None
        self.calls: List = []  # FileControlEntryCall
        self.file_description_entry: "Optional[FileDescriptionEntry]" = None

    def add_call(self, call) -> None:
        self.calls.append(call)


class FileControlParagraph(CobolDivisionElement):
    """The FILE-CONTROL paragraph: holds the SELECT entries."""

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self._entries: List[FileControlEntry] = []
        self._by_name: Dict[Optional[str], List[FileControlEntry]] = {}

    def add_file_control_entry(self, ctx) -> FileControlEntry:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = FileControlEntry(name, self.program_unit, ctx)
            self._populate_entry(result, ctx)
            self._entries.append(result)
            self._by_name.setdefault(_symbol(name), []).append(result)
            self._register(result)
        return result

    @staticmethod
    def _populate_entry(entry: FileControlEntry, ctx) -> None:
        # Minimal clause capture (raw text); full clause objects deferred.
        select = ctx.selectClause() if hasattr(ctx, "selectClause") else None
        if select is not None:
            entry.organization = select.getText()
        assign_clauses = ctx.assignClause() if hasattr(ctx, "assignClause") else None
        if assign_clauses:
            entry.assign = assign_clauses[0].getText()

    @property
    def file_control_entries(self) -> List[FileControlEntry]:
        return self._entries

    def get_file_control_entry(self, name: str) -> Optional[FileControlEntry]:
        entries = self._by_name.get(_symbol(name), [])
        return entries[0] if entries else None


class InputOutputSection(CobolDivisionElement):
    """INPUT-OUTPUT SECTION: file-control + i-o-control paragraphs."""

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.file_control_paragraph: Optional[FileControlParagraph] = None
        self.io_control_paragraph: Optional[IoControlParagraph] = None

    def add_file_control_paragraph(self, ctx) -> FileControlParagraph:
        result = self._get_element(ctx)
        if result is None:
            result = FileControlParagraph(self.program_unit, ctx)
            for entry_ctx in ctx.fileControlEntry():
                result.add_file_control_entry(entry_ctx)
            self.file_control_paragraph = result
            self._register(result)
        return result

    def add_io_control_paragraph(self, ctx) -> IoControlParagraph:
        result = self._get_element(ctx)
        if result is None:
            result = IoControlParagraph(self.program_unit, ctx)
            self.io_control_paragraph = result
            self._register(result)
        return result


class EnvironmentDivision(CobolDivisionElement):
    """ENVIRONMENT DIVISION: configuration, input-output, special-names."""

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.configuration_section: Optional[ConfigurationSection] = None
        self.input_output_section: Optional[InputOutputSection] = None
        self.special_names_paragraph: Optional[SpecialNamesParagraph] = None

    def add_configuration_section(self, ctx) -> ConfigurationSection:
        result = self._get_element(ctx)
        if result is None:
            result = ConfigurationSection(self.program_unit, ctx)
            self.configuration_section = result
            self._register(result)
        return result

    def add_special_names_paragraph(self, ctx) -> SpecialNamesParagraph:
        result = self._get_element(ctx)
        if result is None:
            result = SpecialNamesParagraph(self.program_unit, ctx)
            self.special_names_paragraph = result
            self._register(result)
        return result

    def add_input_output_section(self, ctx) -> InputOutputSection:
        result = self._get_element(ctx)
        if result is None:
            result = InputOutputSection(self.program_unit, ctx)
            for paragraph_ctx in ctx.inputOutputSectionParagraph():
                if paragraph_ctx.fileControlParagraph() is not None:
                    result.add_file_control_paragraph(paragraph_ctx.fileControlParagraph())
                elif paragraph_ctx.ioControlParagraph() is not None:
                    result.add_io_control_paragraph(paragraph_ctx.ioControlParagraph())
            self.input_output_section = result
            self._register(result)
        return result
