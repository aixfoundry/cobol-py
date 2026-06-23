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


# ============================================================================
# Report Section (28 models — IBM mainframe report writer)
# ============================================================================

class ReportSection(CobolDivisionElement):
    """REPORT SECTION: holds ReportDescription entries."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.report_descriptions: List = []
        self._by_name: Dict[Optional[str], object] = {}

    def add_report_description(self, ctx):
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx.reportName())
            result = ReportDescription(name, self.program_unit, ctx)
            rd_entry = ctx.reportDescriptionEntry()
            if rd_entry is not None:
                result.add_report_description_entry(rd_entry)
            self._save(name, result)
        return result

    def _save(self, name, entry):
        self.report_descriptions.append(entry)
        self._by_name[_symbol(name)] = entry
        self._register(entry)

    def get_report_description(self, name: str):
        return self._by_name.get(_symbol(name))


class ReportDescription(CobolDivisionElement, Declaration):
    """A named report within REPORT SECTION."""

    def __init__(self, name, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name
        self.calls: List = []
        self.report_description_entry: Optional[ReportDescriptionEntry] = None
        self.report_group_description_entries: List[ReportGroupDescriptionEntry] = []
        self._rg_by_name: Dict[Optional[str], List] = {}

    def add_call(self, call) -> None:
        self.calls.append(call)

    def add_report_description_entry(self, ctx):
        result = self._get_element(ctx)
        if result is None:
            result = ReportDescriptionEntry(self.program_unit, ctx)
            gctx = getattr(ctx, "reportDescriptionGlobalClause", lambda: None)()
            if gctx is not None:
                result.add_global_clause(gctx)
            pdctx = getattr(ctx, "reportDescriptionPageLimitClause", lambda: None)()
            if pdctx is not None:
                result.add_page_limit_clause(pdctx)
            # heading/footing/first/last detail
            for (acc, builder) in [
                ("reportDescriptionHeadingClause", "add_heading_clause"),
                ("reportDescriptionFootingClause", "add_footing_clause"),
                ("reportDescriptionFirstDetailClause", "add_first_detail_clause"),
                ("reportDescriptionLastDetailClause", "add_last_detail_clause"),
            ]:
                cctx = getattr(ctx, acc, lambda: None)()
                if cctx is not None:
                    getattr(result, builder)(cctx)
            self._register(result)
        self.report_description_entry = result
        return result

    def _register_rg(self, name, entry):
        self.report_group_description_entries.append(entry)
        self._rg_by_name.setdefault(_symbol(name), []).append(entry)

    def get_report_group_description_entries(self, name=None):
        if name:
            return self._rg_by_name.get(_symbol(name), [])
        return self.report_group_description_entries

    def get_report_group_description_entry(self, name):
        entries = self._rg_by_name.get(_symbol(name), [])
        return entries[0] if entries else None


class ReportDescriptionEntry(CobolDivisionElement):
    """Descriptor entry for a report (Global, PageLimit, Heading, Footing, Detail)."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.global_clause = None
        self.page_limit_clause = None
        self.heading_clause = None
        self.footing_clause = None
        self.first_detail_clause = None
        self.last_detail_clause = None

    def _intlit(self, ctx):
        il = getattr(ctx, "integerLiteral", lambda: None)()
        return self.create_integer_literal(il) if il else None

    def add_global_clause(self, ctx):
        g = self._get_element(ctx)
        if g is None:
            g = ReportGlobalClause(self.program_unit, ctx)
            g.global_ = getattr(ctx, "GLOBAL", lambda: None)() is not None
            self._register(g)
        self.global_clause = g
        return g

    def add_page_limit_clause(self, ctx):
        p = self._get_element(ctx)
        if p is None:
            p = ReportPageLimitClause(self.program_unit, ctx)
            p.page_limit_integer_literal = self._intlit(ctx)
            self._register(p)
        self.page_limit_clause = p
        return p

    def add_heading_clause(self, ctx):
        h = self._get_element(ctx)
        if h is None:
            h = ReportHeadingClause(self.program_unit, ctx)
            h.heading_integer_literal = self._intlit(ctx)
            self._register(h)
        self.heading_clause = h
        return h

    def add_footing_clause(self, ctx):
        f = self._get_element(ctx)
        if f is None:
            f = ReportFootingClause(self.program_unit, ctx)
            f.footing_integer_literal = self._intlit(ctx)
            self._register(f)
        self.footing_clause = f
        return f

    def add_first_detail_clause(self, ctx):
        fd = self._get_element(ctx)
        if fd is None:
            fd = ReportFirstDetailClause(self.program_unit, ctx)
            fd.first_detail_integer_literal = self._intlit(ctx)
            self._register(fd)
        self.first_detail_clause = fd
        return fd

    def add_last_detail_clause(self, ctx):
        ld = self._get_element(ctx)
        if ld is None:
            ld = ReportLastDetailClause(self.program_unit, ctx)
            ld.last_detail_integer_literal = self._intlit(ctx)
            self._register(ld)
        self.last_detail_clause = ld
        return ld


# -- Report description entry clauses (6 types) ------------------------------

class ReportGlobalClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.global_: bool = False


class ReportPageLimitClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.page_limit_integer_literal = None


class ReportHeadingClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.heading_integer_literal = None


class ReportFootingClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.footing_integer_literal = None


class ReportFirstDetailClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.first_detail_integer_literal = None


class ReportLastDetailClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.last_detail_integer_literal = None


# -- Report group entry types -------------------------------------------------

class ReportGroupDescriptionEntryType(Enum):
    PRINTABLE = "PRINTABLE"
    SINGLE = "SINGLE"
    VERTICAL = "VERTICAL"


class ReportGroupLineNumberType(Enum):
    NEXT_PAGE = "NEXT_PAGE"
    PLUS = "PLUS"


class ReportGroupNextGroupType(Enum):
    ABSOLUTE = "ABSOLUTE"
    NEXT_PAGE = "NEXT_PAGE"
    PLUS = "PLUS"


class ReportGroupTypeClauseType(Enum):
    CONTROL_FOOTING = "CONTROL_FOOTING"
    CONTROL_HEADING = "CONTROL_HEADING"
    DETAIL = "DETAIL"
    PAGE_FOOTING = "PAGE_FOOTING"
    PAGE_HEADING = "PAGE_HEADING"
    REPORT_FOOTING = "REPORT_FOOTING"
    REPORT_HEADING = "REPORT_HEADING"


class ReportGroupUsageType(Enum):
    DISPLAY = "DISPLAY"
    DISPLAY_1 = "DISPLAY_1"


class ReportGroupDescriptionEntry(CobolDivisionElement, Declaration):
    """Base for VERTICAL / SINGLE / PRINTABLE report group entries."""

    def __init__(self, name, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name
        self.level_number: Optional[int] = None
        self.parent_report_group_description_entry = None
        self.report_group_description_entries: List[ReportGroupDescriptionEntry] = []
        self._rg_by_name: Dict[Optional[str], List] = {}
        self.usage_clause = None
        self.line_number_clause = None

    @property
    def report_group_description_entry_type(self) -> ReportGroupDescriptionEntryType:
        raise NotImplementedError

    def register_sub_group(self, entry):
        name = getattr(entry, "name", None)
        self.report_group_description_entries.append(entry)
        self._rg_by_name.setdefault(_symbol(name), []).append(entry)

    def get_report_group_description_entry(self, name):
        entries = self._rg_by_name.get(_symbol(name), [])
        return entries[0] if entries else None

    def add_group_usage_clause(self, ctx):
        u = self._get_element(ctx)
        if u is None:
            u = ReportGroupUsageClause(self.program_unit, ctx)
            if getattr(ctx, "DISPLAY_1", lambda: None)() is not None:
                u.usage_clause_type = ReportGroupUsageType.DISPLAY_1
            else:
                u.usage_clause_type = ReportGroupUsageType.DISPLAY
            self._register(u)
        self.usage_clause = u
        return u

    def add_line_number_clause(self, ctx):
        ln = self._get_element(ctx)
        if ln is None:
            ln = ReportGroupLineNumberClause(self.program_unit, ctx)
            if getattr(ctx, "NEXT_PAGE", lambda: None)() is not None:
                ln.line_number_clause_type = ReportGroupLineNumberType.NEXT_PAGE
            elif getattr(ctx, "PLUS", lambda: None)() is not None:
                ln.line_number_clause_type = ReportGroupLineNumberType.PLUS
            il = getattr(ctx, "integerLiteral", lambda: None)()
            if il is not None:
                ln.integer_literal = self.create_integer_literal(il)
            self._register(ln)
        self.line_number_clause = ln
        return ln


class ReportGroupDescriptionEntryVertical(ReportGroupDescriptionEntry):
    """VERTICAL report group: NEXT GROUP + TYPE clauses."""

    def __init__(self, name, program_unit, ctx):
        super().__init__(name, program_unit, ctx)
        self.next_group_clause = None
        self.type_clause = None

    @property
    def report_group_description_entry_type(self):
        return ReportGroupDescriptionEntryType.VERTICAL

    def add_next_group_clause(self, ctx):
        ng = self._get_element(ctx)
        if ng is None:
            ng = ReportGroupNextGroupClause(self.program_unit, ctx)
            if getattr(ctx, "NEXT_PAGE", lambda: None)() is not None:
                ng.next_group_clause_type = ReportGroupNextGroupType.NEXT_PAGE
            elif getattr(ctx, "PLUS", lambda: None)() is not None:
                ng.next_group_clause_type = ReportGroupNextGroupType.PLUS
            elif getattr(ctx, "ABSOLUTE", lambda: None)() is not None:
                ng.next_group_clause_type = ReportGroupNextGroupType.ABSOLUTE
            il = getattr(ctx, "integerLiteral", lambda: None)()
            if il is not None:
                ng.integer_literal = self.create_integer_literal(il)
            self._register(ng)
        self.next_group_clause = ng
        return ng

    def add_type_clause(self, ctx):
        tc = self._get_element(ctx)
        if tc is None:
            tc = ReportGroupTypeClause(self.program_unit, ctx)
            for (token, typ) in [
                ("CONTROL_FOOTING", ReportGroupTypeClauseType.CONTROL_FOOTING),
                ("CONTROL_HEADING", ReportGroupTypeClauseType.CONTROL_HEADING),
                ("DETAIL", ReportGroupTypeClauseType.DETAIL),
                ("PAGE_FOOTING", ReportGroupTypeClauseType.PAGE_FOOTING),
                ("PAGE_HEADING", ReportGroupTypeClauseType.PAGE_HEADING),
                ("REPORT_FOOTING", ReportGroupTypeClauseType.REPORT_FOOTING),
                ("REPORT_HEADING", ReportGroupTypeClauseType.REPORT_HEADING),
            ]:
                if getattr(ctx, token, lambda: None)() is not None:
                    tc.type_clause_type = typ
                    break
            dc = getattr(ctx, "dataName", lambda: None)()
            if dc is not None:
                tc.data_call = self.create_call(dc)
            self._register(tc)
        self.type_clause = tc
        return tc


class ReportGroupDescriptionEntrySingle(ReportGroupDescriptionEntry):
    """SINGLE report group: no additional clauses."""

    @property
    def report_group_description_entry_type(self):
        return ReportGroupDescriptionEntryType.SINGLE


class ReportGroupDescriptionEntryPrintable(ReportGroupDescriptionEntry):
    """PRINTABLE report group: PICTURE, SOURCE, SUM, VALUE, etc. (10 clauses)."""

    def __init__(self, name, program_unit, ctx):
        super().__init__(name, program_unit, ctx)
        self.picture_clause = None
        self.source_clause = None
        self.sum_clause = None
        self.value_clause = None
        self.blank_when_zero_clause = None
        self.column_number_clause = None
        self.group_indicate_clause = None
        self.justified_clause = None
        self.reset_clause = None
        self.sign_clause = None

    @property
    def report_group_description_entry_type(self):
        return ReportGroupDescriptionEntryType.PRINTABLE

    def _bld(self, cls, attr, ctx, **fields):
        r = self._get_element(ctx)
        if r is None:
            r = cls(self.program_unit, ctx)
            for k, v in fields.items():
                setattr(r, k, v)
            self._register(r)
        setattr(self, attr, r)
        return r

    def add_picture_clause(self, ctx):
        return self._bld(ReportGroupPictureClause, "picture_clause", ctx,
                         picture_string=ctx.getText())

    def add_source_clause(self, ctx):
        return self._bld(ReportGroupSourceClause, "source_clause", ctx,
                         source_call=self.create_call(ctx.identifier()) if ctx.identifier() else None)

    def add_value_clause(self, ctx):
        return self._bld(ReportGroupValueClause, "value_clause", ctx,
                         literal=self.create_literal(ctx.literal()) if ctx.literal() else None)

    def add_blank_when_zero_clause(self, ctx):
        return self._bld(ReportGroupBlankWhenZeroClause, "blank_when_zero_clause", ctx,
                         blank_when_zero=True)

    def add_column_number_clause(self, ctx):
        return self._bld(ReportGroupColumnNumberClause, "column_number_clause", ctx,
                         integer_literal=self.create_integer_literal(
                             ctx.integerLiteral()) if ctx.integerLiteral() else None)

    def add_group_indicate_clause(self, ctx):
        return self._bld(ReportGroupIndicateClause, "group_indicate_clause", ctx,
                         indicate=True)

    def add_justified_clause(self, ctx):
        jt = ReportGroupJustified.RIGHT if (
            getattr(ctx, "RIGHT", lambda: None)() is not None
        ) else ReportGroupJustified.JUSTIFIED
        return self._bld(ReportGroupJustifiedClause, "justified_clause", ctx,
                         justified=jt)

    def add_reset_clause(self, ctx):
        return self._bld(ReportGroupResetClause, "reset_clause", ctx,
                         data_call=self.create_call(ctx.dataName()) if ctx.dataName() else None)

    def add_sign_clause(self, ctx):
        st = ReportGroupSignType.TRAILING if (
            getattr(ctx, "TRAILING", lambda: None)() is not None
        ) else ReportGroupSignType.LEADING
        return self._bld(ReportGroupSignClause, "sign_clause", ctx,
                         sign_clause_type=st,
                         separate=getattr(ctx, "SEPARATE", lambda: None)() is not None)

    def add_sum_clause(self, ctx):
        r = self._get_element(ctx)
        if r is None:
            r = ReportGroupSumClause(self.program_unit, ctx)
            for qdn in getattr(ctx, "qualifiedDataName", lambda: [])():
                r.add_sum_call(self.create_call(qdn))
            self._register(r)
        self.sum_clause = r
        return r


# -- Report group clause classes (15 types) ----------------------------------

class ReportGroupJustified(Enum):
    JUSTIFIED = "JUSTIFIED"
    RIGHT = "RIGHT"


class ReportGroupSignType(Enum):
    LEADING = "LEADING"
    TRAILING = "TRAILING"


class ReportGroupBlankWhenZeroClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.blank_when_zero: bool = False


class ReportGroupColumnNumberClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.integer_literal = None


class ReportGroupIndicateClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.indicate: bool = False


class ReportGroupJustifiedClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.justified: Optional[ReportGroupJustified] = None


class ReportGroupLineNumberClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.line_number_clause_type: Optional[ReportGroupLineNumberType] = None
        self.integer_literal = None


class ReportGroupNextGroupClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.next_group_clause_type: Optional[ReportGroupNextGroupType] = None
        self.integer_literal = None


class ReportGroupPictureClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.picture_string: Optional[str] = None


class ReportGroupResetClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_call = None


class ReportGroupSignClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.sign_clause_type: Optional[ReportGroupSignType] = None
        self.separate: bool = False


class ReportGroupSourceClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.source_call = None


class ReportGroupSumClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.sum_calls: List = []
        self.upon_calls: List = []

    def add_sum_call(self, call):
        self.sum_calls.append(call)

    def add_upon_call(self, call):
        self.upon_calls.append(call)


class ReportGroupTypeClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.type_clause_type: Optional[ReportGroupTypeClauseType] = None
        self.data_call = None


class ReportGroupUsageClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.usage_clause_type: Optional[ReportGroupUsageType] = None


class ReportGroupValueClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.literal = None


# ============================================================================
# Screen Section (31 models — IBM mainframe screen description)
# ============================================================================

class ScreenSection(CobolDivisionElement):
    """SCREEN SECTION: holds ScreenDescriptionEntry nodes."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.screen_description_entries: List[ScreenDescriptionEntry] = []
        self._root_entries: List[ScreenDescriptionEntry] = []
        self._by_name: Dict[Optional[str], List[ScreenDescriptionEntry]] = {}

    def _save(self, entry):
        self.screen_description_entries.append(entry)
        name = getattr(entry, "name", None)
        self._by_name.setdefault(_symbol(name), []).append(entry)
        self._register(entry)

    def add_screen_description_entry(self, ctx):
        # ctx is ScreenDescriptionEntryContext
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = ScreenDescriptionEntry(name, self.program_unit, ctx)
            self._populate_screen_clauses(result, ctx)
            self._save(result)
        return result

    def _populate_screen_clauses(self, entry, ctx):
        # Build standard entries first
        entry._build_all(ctx)

    @property
    def root_screen_description_entries(self):
        return self._root_entries

    def get_screen_description_entries(self, name=None):
        if name:
            return self._by_name.get(_symbol(name), [])
        return self.screen_description_entries

    def get_screen_description_entry(self, name):
        entries = self._by_name.get(_symbol(name), [])
        return entries[0] if entries else None


# -- Screen clause enums ------------------------------------------------------

class ScreenAutoType(Enum):
    AUTO = "AUTO"
    AUTO_SKIP = "AUTO_SKIP"


class ScreenBellType(Enum):
    BEEP = "BEEP"
    BELL = "BELL"


class ScreenBlankType(Enum):
    LINE = "LINE"
    SCREEN = "SCREEN"


class ScreenColumnType(Enum):
    EQUAL = "EQUAL"
    MINUS = "MINUS"
    PLUS = "PLUS"


class ScreenEraseType(Enum):
    EOL = "EOL"
    EOS = "EOS"


class ScreenFullType(Enum):
    FULL = "FULL"
    LENGTH_CHECK = "LENGTH_CHECK"


class ScreenGridType(Enum):
    GRID = "GRID"
    LEFTLINE = "LEFTLINE"
    OVERLINE = "OVERLINE"


class ScreenLightType(Enum):
    HIGHLIGHT = "HIGHLIGHT"
    LOWLIGHT = "LOWLIGHT"


class ScreenRequiredType(Enum):
    EMPTY_CHECK = "EMPTY_CHECK"
    REQUIRED = "REQUIRED"


class ScreenSecureType(Enum):
    NO_ECHO = "NO_ECHO"
    SECURE = "SECURE"


class ScreenSignType(Enum):
    LEADING = "LEADING"
    TRAILING = "TRAILING"


class ScreenUsageType(Enum):
    DISPLAY = "DISPLAY"
    DISPLAY_1 = "DISPLAY_1"


class ScreenJustified(Enum):
    JUSTIFIED = "JUSTIFIED"
    RIGHT = "RIGHT"


# -- Screen sub-models --------------------------------------------------------

class ScreenTo(CobolDivisionElement):
    """TO identifier within ScreenDescriptionFromClause."""
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.to_call = None


class ScreenOccurs(CobolDivisionElement):
    """OCCURS integerLiteral TIMES for PromptClause."""
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.occurs_times = None


class ScreenDescriptionEntry(CobolDivisionElement, Declaration):
    """One screen description entry (level 01-49): holds up to 28 clause types."""

    def __init__(self, name, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name
        self.level_number: Optional[int] = None
        self.filler: Optional[bool] = None
        self.parent_screen_description_entry = None
        self.predecessor = None
        self.successor = None
        self.calls: List = []
        self._sub_entries: List[ScreenDescriptionEntry] = []
        self._sub_by_name: Dict[Optional[str], List] = {}
        # 28 clause slots
        self.auto_clause = None
        self.background_color_clause = None
        self.bell_clause = None
        self.blank_clause = None
        self.blank_when_zero_clause = None
        self.blink_clause = None
        self.column_number_clause = None
        self.control_clause = None
        self.erase_clause = None
        self.foreground_color_clause = None
        self.from_clause = None
        self.full_clause = None
        self.grid_clause = None
        self.justified_clause = None
        self.light_clause = None
        self.line_number_clause = None
        self.picture_clause = None
        self.prompt_clause = None
        self.required_clause = None
        self.reverse_video_clause = None
        self.secure_clause = None
        self.sign_clause = None
        self.size_clause = None
        self.underline_clause = None
        self.usage_clause = None
        self.using_clause = None
        self.value_clause = None
        self.zero_fill_clause = None

    def add_call(self, call):
        self.calls.append(call)

    def add_screen_description_entry(self, entry):
        self._sub_entries.append(entry)
        self._sub_by_name.setdefault(_symbol(entry.name), []).append(entry)

    def get_screen_description_entries(self, name=None):
        if name:
            return self._sub_by_name.get(_symbol(name), [])
        return self._sub_entries

    def get_screen_description_entry(self, name):
        entries = self._sub_by_name.get(_symbol(name), [])
        return entries[0] if entries else None

    def _bld(self, cls, attr, ctx, **fields):
        r = self._get_element(ctx)
        if r is None:
            r = cls(self.program_unit, ctx)
            for k, v in fields.items():
                setattr(r, k, v)
            self._register(r)
        setattr(self, attr, r)
        return r

    def _build_all(self, ctx):
        """Build all clauses present on the ctx (called by ScreenSection during pop)."""
        dispatch = {
            "screenDescriptionAutoClause": ("auto_clause", self.add_auto_clause),
            "screenDescriptionBackgroundColorClause": ("bg", self.add_background_color_clause),
            "screenDescriptionBellClause": ("bell", self.add_bell_clause),
            "screenDescriptionBlankClause": ("blank", self.add_blank_clause),
            "screenDescriptionBlankWhenZeroClause": ("bwz", self.add_blank_when_zero_clause),
            "screenDescriptionBlinkClause": ("blink", self.add_blink_clause),
            "screenDescriptionColumnClause": ("col", self.add_column_number_clause),
            "screenDescriptionControlClause": ("ctl", self.add_control_clause),
            "screenDescriptionEraseClause": ("erase", self.add_erase_clause),
            "screenDescriptionForegroundColorClause": ("fg", self.add_foreground_color_clause),
            "screenDescriptionFromClause": ("from", self.add_from_clause),
            "screenDescriptionFullClause": ("full", self.add_full_clause),
            "screenDescriptionGridClause": ("grid", self.add_grid_clause),
            "screenDescriptionJustifiedClause": ("just", self.add_justified_clause_as_scr),
            "screenDescriptionLightClause": ("light", self.add_light_clause),
            "screenDescriptionLineClause": ("line", self.add_line_number_clause),
            "screenDescriptionPictureClause": ("pic", self.add_picture_clause_as_scr),
            "screenDescriptionPromptClause": ("prompt", self.add_prompt_clause),
            "screenDescriptionRequiredClause": ("req", self.add_required_clause),
            "screenDescriptionReverseVideoClause": ("rv", self.add_reverse_video_clause),
            "screenDescriptionSecureClause": ("sec", self.add_secure_clause),
            "screenDescriptionSignClause": ("sign", self.add_sign_clause_as_scr),
            "screenDescriptionSizeClause": ("size", self.add_size_clause_as_scr),
            "screenDescriptionUnderlineClause": ("ul", self.add_underline_clause),
            "screenDescriptionUsageClause": ("usage", self.add_usage_clause_as_scr),
            "screenDescriptionUsingClause": ("using", self.add_using_clause_as_scr),
            "screenDescriptionValueClause": ("val", self.add_value_clause_as_scr),
            "screenDescriptionZeroFillClause": ("zf", self.add_zero_fill_clause),
        }
        for (acc, (_, builder)) in dispatch.items():
            ctxs = getattr(ctx, acc, lambda: [])()
            if ctxs:
                for c in (ctxs if isinstance(ctxs, list) else [ctxs]):
                    builder(c)

    def _clause(self, cls, attr, ctx):
        return self._bld(cls, attr, ctx)

    # -- Auto clause --
    def add_auto_clause(self, ctx):
        t = ScreenAutoType.AUTO_SKIP if getattr(ctx, "AUTO_SKIP", lambda: None)() is not None else ScreenAutoType.AUTO
        return self._clause(ScreenAutoClause, "auto_clause", ctx, auto_clause_type=t)

    # -- Background color --
    def add_background_color_clause(self, ctx):
        return self._clause(ScreenBackgroundColorClause, "background_color_clause", ctx,
                            color_value_stmt=self.create_value_stmt(ctx.identifier(), ctx.literal()) if (ctx.identifier() or ctx.literal()) else None)

    # -- Bell --
    def add_bell_clause(self, ctx):
        t = ScreenBellType.BELL if getattr(ctx, "BELL", lambda: None)() is not None else ScreenBellType.BEEP
        return self._clause(ScreenBellClause, "bell_clause", ctx, bell_clause_type=t)

    # -- Blank --
    def add_blank_clause(self, ctx):
        t = ScreenBlankType.SCREEN if getattr(ctx, "SCREEN", lambda: None)() is not None else ScreenBlankType.LINE
        return self._clause(ScreenBlankClause, "blank_clause", ctx, blank_clause_type=t)

    # -- Blank when zero --
    def add_blank_when_zero_clause(self, ctx):
        return self._clause(ScreenBlankWhenZeroClause, "blank_when_zero_clause", ctx, blank_when_zero=True)

    # -- Blink --
    def add_blink_clause(self, ctx):
        return self._clause(ScreenBlinkClause, "blink_clause", ctx, blink=True)

    # -- Column number --
    def add_column_number_clause(self, ctx):
        t: Optional[ScreenColumnType] = None
        if getattr(ctx, "PLUSCHAR", lambda: None)() is not None:
            t = ScreenColumnType.PLUS
        elif getattr(ctx, "MINUSCHAR", lambda: None)() is not None:
            t = ScreenColumnType.MINUS
        else:
            t = ScreenColumnType.EQUAL
        il = self.create_integer_literal(ctx.integerLiteral()) if ctx.integerLiteral() else None
        return self._clause(ScreenColumnNumberClause, "column_number_clause", ctx,
                            column_number_clause_type=t, integer_literal=il)

    # -- Control --
    def add_control_clause(self, ctx):
        ident = ctx.identifier()
        return self._clause(ScreenControlClause, "control_clause", ctx,
                            control_call=self.create_call(ident) if ident else None)

    # -- Erase --
    def add_erase_clause(self, ctx):
        t = ScreenEraseType.EOS if getattr(ctx, "EOS", lambda: None)() is not None else ScreenEraseType.EOL
        return self._clause(ScreenEraseClause, "erase_clause", ctx, erase_clause_type=t)

    # -- Foreground color --
    def add_foreground_color_clause(self, ctx):
        return self._clause(ScreenForegroundColorClause, "foreground_color_clause", ctx,
                            color_value_stmt=self.create_value_stmt(ctx.identifier(), ctx.literal()) if (ctx.identifier() or ctx.literal()) else None)

    # -- From (with optional TO) --
    def add_from_clause(self, ctx):
        r = self._get_element(ctx)
        if r is None:
            r = ScreenFromClause(self.program_unit, ctx)
            r.from_value_stmt = self.create_value_stmt(ctx.identifier(), ctx.literal()) if (ctx.identifier() or ctx.literal()) else None
            to_ctx = getattr(ctx, "screenDescriptionToClause", lambda: None)()
            if to_ctx is not None:
                r.add_to(to_ctx)
            self._register(r)
        self.from_clause = r
        return r

    # -- Full --
    def add_full_clause(self, ctx):
        t = ScreenFullType.LENGTH_CHECK if getattr(ctx, "LENGTH_CHECK", lambda: None)() is not None else ScreenFullType.FULL
        return self._clause(ScreenFullClause, "full_clause", ctx, full_clause_type=t)

    # -- Grid --
    def add_grid_clause(self, ctx):
        t: ScreenGridType
        if getattr(ctx, "LEFTLINE", lambda: None)() is not None:
            t = ScreenGridType.LEFTLINE
        elif getattr(ctx, "OVERLINE", lambda: None)() is not None:
            t = ScreenGridType.OVERLINE
        else:
            t = ScreenGridType.GRID
        return self._clause(ScreenGridClause, "grid_clause", ctx, grid_clause_type=t)

    # -- Justified --
    def add_justified_clause_as_scr(self, ctx):
        jt = ScreenJustified.RIGHT if getattr(ctx, "RIGHT", lambda: None)() is not None else ScreenJustified.JUSTIFIED
        return self._clause(ScreenJustifiedClause, "justified_clause", ctx, justified=jt)

    # -- Light --
    def add_light_clause(self, ctx):
        t = ScreenLightType.LOWLIGHT if getattr(ctx, "LOWLIGHT", lambda: None)() is not None else ScreenLightType.HIGHLIGHT
        return self._clause(ScreenLightClause, "light_clause", ctx, light_clause_type=t)

    # -- Line number --
    def add_line_number_clause(self, ctx):
        t: Optional[ScreenColumnType] = None
        if getattr(ctx, "PLUSCHAR", lambda: None)() is not None:
            t = ScreenColumnType.PLUS
        elif getattr(ctx, "MINUSCHAR", lambda: None)() is not None:
            t = ScreenColumnType.MINUS
        else:
            t = ScreenColumnType.EQUAL
        il = self.create_integer_literal(ctx.integerLiteral()) if ctx.integerLiteral() else None
        return self._clause(ScreenLineNumberClause, "line_number_clause", ctx,
                            line_number_clause_type=t, integer_literal=il)

    # -- Picture --
    def add_picture_clause_as_scr(self, ctx):
        return self._clause(ScreenPictureClause, "picture_clause", ctx,
                            picture_string=ctx.getText())

    # -- Prompt --
    def add_prompt_clause(self, ctx):
        r = self._get_element(ctx)
        if r is None:
            r = ScreenPromptClause(self.program_unit, ctx)
            r.character_value_stmt = self.create_value_stmt(ctx.identifier(), ctx.literal()) if (ctx.identifier() or ctx.literal()) else None
            occ = getattr(ctx, "screenDescriptionPromptOccursClause", lambda: None)()
            if occ is not None:
                r.add_occurs(occ)
            self._register(r)
        self.prompt_clause = r
        return r

    # -- Required --
    def add_required_clause(self, ctx):
        t = ScreenRequiredType.REQUIRED if getattr(ctx, "REQUIRED", lambda: None)() is not None else ScreenRequiredType.EMPTY_CHECK
        return self._clause(ScreenRequiredClause, "required_clause", ctx, required_clause_type=t)

    # -- Reverse video --
    def add_reverse_video_clause(self, ctx):
        return self._clause(ScreenReverseVideoClause, "reverse_video_clause", ctx, reverse_video=True)

    # -- Secure --
    def add_secure_clause(self, ctx):
        t = ScreenSecureType.NO_ECHO if getattr(ctx, "NO_ECHO", lambda: None)() is not None else ScreenSecureType.SECURE
        return self._clause(ScreenSecureClause, "secure_clause", ctx, secure_clause_type=t)

    # -- Sign --
    def add_sign_clause_as_scr(self, ctx):
        st = ScreenSignType.TRAILING if getattr(ctx, "TRAILING", lambda: None)() is not None else ScreenSignType.LEADING
        return self._clause(ScreenSignClause, "sign_clause", ctx,
                            sign_clause_type=st,
                            separate=getattr(ctx, "SEPARATE", lambda: None)() is not None)

    # -- Size --
    def add_size_clause_as_scr(self, ctx):
        return self._clause(ScreenSizeClause, "size_clause", ctx,
                            size_value_stmt=self.create_value_stmt(ctx.identifier(), ctx.literal()) if (ctx.identifier() or ctx.literal()) else None)

    # -- Underline --
    def add_underline_clause(self, ctx):
        return self._clause(ScreenUnderlineClause, "underline_clause", ctx, underline=True)

    # -- Usage --
    def add_usage_clause_as_scr(self, ctx):
        t = ScreenUsageType.DISPLAY_1 if getattr(ctx, "DISPLAY_1", lambda: None)() is not None else ScreenUsageType.DISPLAY
        return self._clause(ScreenUsageClause, "usage_clause", ctx, usage_clause_type=t)

    # -- Using --
    def add_using_clause_as_scr(self, ctx):
        ident = ctx.identifier()
        return self._clause(ScreenUsingClause, "using_clause", ctx,
                            using_call=self.create_call(ident) if ident else None)

    # -- Value --
    def add_value_clause_as_scr(self, ctx):
        return self._clause(ScreenValueClause, "value_clause", ctx,
                            literal=self.create_literal(ctx.literal()) if ctx.literal() else None)

    # -- Zero fill --
    def add_zero_fill_clause(self, ctx):
        return self._clause(ScreenZeroFillClause, "zero_fill_clause", ctx, zero_fill=True)


# -- Screen clause classes (28 types) -----------------------------------------

class ScreenAutoClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.auto_clause_type: Optional[ScreenAutoType] = None


class ScreenBackgroundColorClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.color_value_stmt = None


class ScreenBellClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.bell_clause_type: Optional[ScreenBellType] = None


class ScreenBlankClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.blank_clause_type: Optional[ScreenBlankType] = None


class ScreenBlankWhenZeroClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.blank_when_zero: bool = False


class ScreenBlinkClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.blink: bool = False


class ScreenColumnNumberClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.column_number_clause_type: Optional[ScreenColumnType] = None
        self.integer_literal = None


class ScreenControlClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.control_call = None


class ScreenEraseClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.erase_clause_type: Optional[ScreenEraseType] = None


class ScreenForegroundColorClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.color_value_stmt = None


class ScreenFromClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.from_value_stmt = None
        self.to: Optional[ScreenTo] = None

    def add_to(self, ctx):
        t = self._get_element(ctx)
        if t is None:
            t = ScreenTo(self.program_unit, ctx)
            ident = getattr(ctx, "identifier", lambda: None)()
            if ident is not None:
                t.to_call = self.create_call(ident)
            self._register(t)
        self.to = t
        return t


class ScreenFullClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.full_clause_type: Optional[ScreenFullType] = None


class ScreenGridClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.grid_clause_type: Optional[ScreenGridType] = None


class ScreenJustifiedClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.justified: Optional[ScreenJustified] = None


class ScreenLightClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.light_clause_type: Optional[ScreenLightType] = None


class ScreenLineNumberClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.line_number_clause_type: Optional[ScreenColumnType] = None
        self.integer_literal = None


class ScreenPictureClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.picture_string: Optional[str] = None


class ScreenPromptClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.character_value_stmt = None
        self.occurs: Optional[ScreenOccurs] = None

    def add_occurs(self, ctx):
        o = self._get_element(ctx)
        if o is None:
            o = ScreenOccurs(self.program_unit, ctx)
            il = getattr(ctx, "integerLiteral", lambda: None)()
            if il is not None:
                o.occurs_times = self.create_integer_literal(il)
            self._register(o)
        self.occurs = o
        return o


class ScreenRequiredClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.required_clause_type: Optional[ScreenRequiredType] = None


class ScreenReverseVideoClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.reverse_video: bool = False


class ScreenSecureClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.secure_clause_type: Optional[ScreenSecureType] = None


class ScreenSignClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.sign_clause_type: Optional[ScreenSignType] = None
        self.separate: bool = False


class ScreenSizeClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.size_value_stmt = None


class ScreenUnderlineClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.underline: bool = False


class ScreenUsageClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.usage_clause_type: Optional[ScreenUsageType] = None


class ScreenUsingClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.using_call = None


class ScreenValueClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.literal = None


class ScreenZeroFillClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.zero_fill: bool = False
