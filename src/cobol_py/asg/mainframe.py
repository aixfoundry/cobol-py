"""Mainframe-only data section models (Phase D4).

Ports ``metamodel/data/database`` and ``metamodel/data/programlibrary`` —
rare mainframe COBOL features. Report and Screen sections are deferred.

DatabaseSection: holds DataBaseSectionEntry nodes (integer literal + 2 value stmts).
ProgramLibrarySection: holds Export/Import library description entries with
attribute, clause, and procedure sub-models.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

from antlr4.ParserRuleContext import ParserRuleContext

from .base import CobolDivisionElement, Declaration

if TYPE_CHECKING:
    from .program import ProgramUnit


def _symbol(name: Optional[str]) -> Optional[str]:
    if name is None or name == "":
        return name
    return name.upper()


# ============================================================================
# DatabaseSection
# ============================================================================

class DataBaseSectionEntry(CobolDivisionElement):
    """One entry in the DATABASE SECTION: integer literal + two value statements."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.integer_literal = None
        self.value_stmt1 = None
        self.value_stmt2 = None


class DataBaseSection(CobolDivisionElement):
    """The DATABASE SECTION: contains database section entries."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_base_section_entries: List[DataBaseSectionEntry] = []

    def add_data_base_section_entry(self, ctx) -> DataBaseSectionEntry:
        result = self._get_element(ctx)
        if result is None:
            result = DataBaseSectionEntry(self.program_unit, ctx)
            if ctx.integerLiteral() is not None:
                result.integer_literal = self.create_integer_literal(ctx.integerLiteral())
            literals = ctx.literal()
            if len(literals) >= 1:
                result.value_stmt1 = self.create_value_stmt(literals[0])
            if len(literals) >= 2:
                result.value_stmt2 = self.create_value_stmt(literals[1])
            self.data_base_section_entries.append(result)
            self._register(result)
        return result


# ============================================================================
# ProgramLibrarySection
# ============================================================================

class LibraryDescriptionEntryType(Enum):
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"


# -- Shared clause models ----------------------------------------------------

class CommonClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.common = False


class GlobalClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.global_ = False


class ForClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.for_literal = None


class GivingClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.giving_call = None


class ImportAttributeSharing(Enum):
    DONT_CARE = "DONT_CARE"
    PRIVATE = "PRIVATE"
    SHARED_BY_ALL = "SHARED_BY_ALL"
    SHARED_BY_RUN_UNIT = "SHARED_BY_RUN_UNIT"


class ImportAttributeType(Enum):
    BY_FUNCTION = "BY_FUNCTION"
    BY_TITLE = "BY_TITLE"


class ExportAttribute(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.sharing: Optional[ImportAttributeSharing] = None


class ImportAttribute(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.import_attribute_type: Optional[ImportAttributeType] = None
        self.function_literal = None
        self.parameter_literal = None
        self.title_literal = None


class LibraryUsingClause(CobolDivisionElement):
    """USING clause for import entry procedures: list of value statements."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.using_value_stmts: List = []


class LibraryWithClause(CobolDivisionElement):
    """WITH clause for import entry procedures: list of value statements."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.with_value_stmts: List = []


class ExportEntryProcedure(CobolDivisionElement):
    """Entry procedure for EXPORT: program call + optional FOR clause."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.program_call = None
        self.for_clause: Optional[ForClause] = None


class ImportEntryProcedure(CobolDivisionElement):
    """Entry procedure for IMPORT: program call + USING/GIVING/WITH/FOR clauses."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.program_call = None
        self.using_clause: Optional[LibraryUsingClause] = None
        self.giving_clause: Optional[GivingClause] = None
        self.with_clause: Optional[LibraryWithClause] = None
        self.for_clause: Optional[ForClause] = None


# -- Library description entries ---------------------------------------------

class LibraryDescriptionEntry(CobolDivisionElement, Declaration):
    """Base for EXPORT / IMPORT library entries."""

    def __init__(self, name, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name

    @property
    def library_description_entry_type(self) -> LibraryDescriptionEntryType:
        raise NotImplementedError


class LibraryDescriptionEntryExport(LibraryDescriptionEntry):
    """Format1: EXPORT library entry with attribute and entry procedure."""

    def __init__(self, name, program_unit, ctx):
        super().__init__(name, program_unit, ctx)
        self.export_attribute: Optional[ExportAttribute] = None
        self.export_entry_procedure: Optional[ExportEntryProcedure] = None

    @property
    def library_description_entry_type(self):
        return LibraryDescriptionEntryType.EXPORT

    def add_export_attribute(self, ctx):
        result = self._get_element(ctx)
        if result is None:
            result = ExportAttribute(self.program_unit, ctx)
            # sharing type
            if getattr(ctx, "DONTCARE", lambda: None)() is not None:
                result.sharing = ImportAttributeSharing.DONT_CARE
            elif getattr(ctx, "PRIVATE", lambda: None)() is not None:
                result.sharing = ImportAttributeSharing.PRIVATE
            elif getattr(ctx, "SHAREDBYALL", lambda: None)() is not None:
                result.sharing = ImportAttributeSharing.SHARED_BY_ALL
            elif getattr(ctx, "SHAREDBYRUNUNIT", lambda: None)() is not None:
                result.sharing = ImportAttributeSharing.SHARED_BY_RUN_UNIT
            self._register(result)
        self.export_attribute = result
        return result

    def add_export_entry_procedure(self, ctx):
        result = self._get_element(ctx)
        if result is None:
            result = ExportEntryProcedure(self.program_unit, ctx)
            pn = getattr(ctx, "programName", lambda: None)()
            if pn is not None:
                result.program_call = self.create_call(pn)
            fc = getattr(ctx, "libraryEntryProcedureForClause", lambda: None)()
            if fc is not None:
                fcl = ForClause(self.program_unit, fc)
                lit = getattr(fc, "literal", lambda: None)()
                if lit is not None:
                    fcl.for_literal = self.create_literal(lit)
                self._register(fcl)
                result.for_clause = fcl
            self._register(result)
        self.export_entry_procedure = result
        return result


class LibraryDescriptionEntryImport(LibraryDescriptionEntry):
    """Format2: IMPORT library entry with common/global/attributes/entry procedures."""

    def __init__(self, name, program_unit, ctx):
        super().__init__(name, program_unit, ctx)
        self.common_clause: Optional[CommonClause] = None
        self.global_clause: Optional[GlobalClause] = None
        self.import_attributes: List[ImportAttribute] = []
        self.import_entry_procedures: List[ImportEntryProcedure] = []

    @property
    def library_description_entry_type(self):
        return LibraryDescriptionEntryType.IMPORT

    def add_common_clause(self, ctx):
        result = self._get_element(ctx)
        if result is None:
            result = CommonClause(self.program_unit, ctx)
            result.common = getattr(ctx, "COMMON", lambda: None)() is not None
            self._register(result)
        self.common_clause = result
        return result

    def add_global_clause(self, ctx):
        result = self._get_element(ctx)
        if result is None:
            result = GlobalClause(self.program_unit, ctx)
            result.global_ = getattr(ctx, "GLOBAL", lambda: None)() is not None
            self._register(result)
        self.global_clause = result
        return result

    def add_import_attribute(self, ctx):
        result = self._get_element(ctx)
        if result is None:
            result = ImportAttribute(self.program_unit, ctx)
            # type: BY FUNCTION or BY TITLE
            if getattr(ctx, "FUNCTION", lambda: None)() is not None:
                result.import_attribute_type = ImportAttributeType.BY_FUNCTION
                fl = getattr(ctx, "functionLiteral", lambda: None)()
                if fl is not None:
                    result.function_literal = fl.getText()
                pl = getattr(ctx, "parameterLiteral", lambda: None)()
                if pl is not None:
                    result.parameter_literal = pl.getText()
            elif getattr(ctx, "TITLE", lambda: None)() is not None:
                result.import_attribute_type = ImportAttributeType.BY_TITLE
                tl = getattr(ctx, "titleLiteral", lambda: None)()
                if tl is not None:
                    result.title_literal = tl.getText()
            self.import_attributes.append(result)
            self._register(result)
        return result

    def add_import_entry_procedure(self, ctx):
        result = self._get_element(ctx)
        if result is None:
            result = ImportEntryProcedure(self.program_unit, ctx)
            pn = getattr(ctx, "programName", lambda: None)()
            if pn is not None:
                result.program_call = self.create_call(pn)
            # USING
            uc = getattr(ctx, "libraryEntryProcedureUsingClause", lambda: None)()
            if uc is not None:
                ucl = LibraryUsingClause(self.program_unit, uc)
                for name_ctx in getattr(uc, "libraryEntryProcedureUsingName", lambda: [])():
                    ucl.using_value_stmts.append(self.create_value_stmt(name_ctx.literal()))
                self._register(ucl)
                result.using_clause = ucl
            # GIVING
            gc = getattr(ctx, "libraryEntryProcedureGivingClause", lambda: None)()
            if gc is not None:
                gcl = GivingClause(self.program_unit, gc)
                gcl.giving_call = self.create_call(
                    getattr(gc, "libraryEntryProcedureGivingName", lambda: None)()
                )
                self._register(gcl)
                result.giving_clause = gcl
            # WITH
            wc = getattr(ctx, "libraryEntryProcedureWithClause", lambda: None)()
            if wc is not None:
                wcl = LibraryWithClause(self.program_unit, wc)
                for name_ctx in getattr(wc, "libraryEntryProcedureWithName", lambda: [])():
                    wcl.with_value_stmts.append(self.create_value_stmt(name_ctx.literal()))
                self._register(wcl)
                result.with_clause = wcl
            # FOR
            fc = getattr(ctx, "libraryEntryProcedureForClause", lambda: None)()
            if fc is not None:
                fcl = ForClause(self.program_unit, fc)
                lit = getattr(fc, "literal", lambda: None)()
                if lit is not None:
                    fcl.for_literal = self.create_literal(lit)
                self._register(fcl)
                result.for_clause = fcl
            self.import_entry_procedures.append(result)
            self._register(result)
        return result


# -- ProgramLibrarySection container -----------------------------------------

class ProgramLibrarySection(CobolDivisionElement):
    """The PROGRAM-LIBRARY SECTION: holds EXPORT/IMPORT library description entries."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.library_description_entries: List[LibraryDescriptionEntry] = []
        self._by_name: Dict[Optional[str], LibraryDescriptionEntry] = {}

    def create_library_description_entry(self, ctx) -> Optional[LibraryDescriptionEntry]:
        fmt1 = getattr(ctx, "libraryDescriptionEntryFormat1", lambda: None)()
        fmt2 = getattr(ctx, "libraryDescriptionEntryFormat2", lambda: None)()
        if fmt1 is not None:
            return self._add_export(fmt1)
        elif fmt2 is not None:
            return self._add_import(fmt2)
        return None

    def _add_export(self, ctx) -> LibraryDescriptionEntryExport:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx.libraryName())
            result = LibraryDescriptionEntryExport(name, self.program_unit, ctx)
            a1 = getattr(ctx, "libraryAttributeClauseFormat1", lambda: None)()
            if a1 is not None:
                result.add_export_attribute(a1)
            ep = getattr(ctx, "libraryEntryProcedureClauseFormat1", lambda: None)()
            if ep is not None:
                result.add_export_entry_procedure(ep)
            self._save(name, result)
        return result

    def _add_import(self, ctx) -> LibraryDescriptionEntryImport:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx.libraryName())
            result = LibraryDescriptionEntryImport(name, self.program_unit, ctx)
            gc = getattr(ctx, "libraryIsGlobalClause", lambda: None)()
            if gc is not None:
                result.add_global_clause(gc)
            cc = getattr(ctx, "libraryIsCommonClause", lambda: None)()
            if cc is not None:
                result.add_common_clause(cc)
            for a2 in getattr(ctx, "libraryAttributeClauseFormat2", lambda: [])():
                result.add_import_attribute(a2)
            for ep in getattr(ctx, "libraryEntryProcedureClauseFormat2", lambda: [])():
                result.add_import_entry_procedure(ep)
            self._save(name, result)
        return result

    def _save(self, name, entry):
        self.library_description_entries.append(entry)
        self._by_name[_symbol(name)] = entry
        self._register(entry)

    def get_library_description_entry(self, name: str):
        return self._by_name.get(_symbol(name))
