"""Call / value-statement / literal factory.

Ports the build helpers of ``metamodel/impl/ProgramUnitElementImpl``
(``createCall``, ``createValueStmt``, ``create*Literal``, ``find*``). Mixed into
:class:`~cobol_py.asg.base.ProgramUnitElement` so every statement and clause
can build references and operands relative to its program unit.

Heavy imports (``call``/``valuestmt``/``literal``/``CobolParser``) are done
lazily inside each method to avoid a module-level cycle with :mod:`base`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from antlr4.ParserRuleContext import ParserRuleContext

if TYPE_CHECKING:
    from .base import ProgramUnit


def _symbol(name: Optional[str]) -> Optional[str]:
    """Upper-case a name for symbol-table comparison (None/"" pass through)."""
    if name is None or name == "":
        return name
    return name.upper()


class ProcedureUnitFactory:
    """Mixin: builds Calls, ValueStmts and literals from AST contexts.

    Relies on the host class providing ``self.program_unit``, ``self._register``,
    ``self._get_element`` and ``self.determine_name`` (all on :class:`ASGElement`).
    """

    # -- symbol lookups ------------------------------------------------------

    def find_paragraph(self, name: Optional[str]):
        pd = self.program_unit.procedure_division
        return pd.get_paragraph(name) if pd is not None else None

    def find_section(self, name: Optional[str]):
        pd = self.program_unit.procedure_division
        return pd.get_section(name) if pd is not None else None

    def find_data_description_entries(self, name: Optional[str]) -> List:
        """Search the data-division sections for entries named ``name``.

        Mirrors ``ProgramUnitElementImpl.findDataDescriptionEntries``: scans
        working-storage, file (FD records), communication, linkage and local
        storage sections. (Report/screen sections are deferred.)
        """
        dd = self.program_unit.data_division
        if dd is None:
            return []
        result: List = []
        for section in (
            dd.working_storage_section,
            dd.communication_section,
            dd.linkage_section,
            dd.local_storage_section,
        ):
            if section is not None:
                result.extend(section.get_data_description_entries(name))
        if dd.file_section is not None:
            for fd in dd.file_section.file_description_entries:
                result.extend(fd.get_data_description_entries(name))
        return result

    def find_file_control_paragraph(self):
        ed = self.program_unit.environment_division
        ios = ed.input_output_section if ed is not None else None
        return ios.file_control_paragraph if ios is not None else None

    def find_file_control_entry(self, name: Optional[str]):
        fcp = self.find_file_control_paragraph()
        return fcp.get_file_control_entry(name) if fcp is not None else None

    # -- calls ---------------------------------------------------------------

    def create_call(self, ctx: Optional[ParserRuleContext]):
        """Build (and register) the :class:`Call` for ``ctx``.

        Ports ``ProgramUnitElementImpl.createCall(ParserRuleContext...)``:
        dispatches on the runtime ctx type across all reference forms
        (qualified data names, special registers, table calls, functions,
        procedures, files, reports, ...). Unresolved references fall back to
        :class:`UndefinedCall`, matching Java.
        """
        if ctx is None:
            return None
        existing = self._get_element(ctx)
        if existing is not None:
            return existing

        from ..CobolParser import CobolParser as CP

        # Identifier wraps its inner reference in a CallDelegate.
        if isinstance(ctx, CP.IdentifierContext):
            return self._create_identifier_call(ctx)
        # Qualified data names (IN/OF qualification, subscripts-as-format, ...).
        if isinstance(ctx, CP.QualifiedDataNameContext):
            return self._create_qualified_data_name_call(ctx)
        if isinstance(ctx, CP.QualifiedDataNameFormat1Context):
            return self._create_qualified_data_name_format1_call(ctx)
        if isinstance(ctx, CP.QualifiedDataNameFormat2Context):
            return self._create_qualified_data_name_format2_call(ctx)
        if isinstance(ctx, CP.QualifiedDataNameFormat3Context):
            text_name = getattr(ctx, "textName", lambda: None)()
            return self.create_call(text_name)
        if isinstance(ctx, CP.QualifiedDataNameFormat4Context):
            return self._create_undefined_call(ctx)
        # Subscripted / special / function references.
        if isinstance(ctx, CP.TableCallContext):
            return self._create_table_call(ctx)
        if isinstance(ctx, CP.SpecialRegisterContext):
            return self._create_special_register_call(ctx)
        if isinstance(ctx, CP.FunctionCallContext):
            return self._create_function_call(ctx)
        # Named declarations.
        if isinstance(ctx, CP.ProcedureNameContext):
            return self._create_procedure_name_call(ctx)
        if isinstance(ctx, CP.FileNameContext):
            return self._create_file_control_call(ctx)
        if isinstance(ctx, CP.ReportNameContext):
            return self._create_report_call(ctx)
        if isinstance(ctx, CP.CdNameContext):
            return self._create_cd_name_call(ctx)
        if isinstance(ctx, CP.MnemonicNameContext):
            return self._create_mnemonic_call(ctx)
        if isinstance(ctx, CP.EnvironmentNameContext):
            return self._create_environment_call(ctx)
        # Data-referencing leaf names funnel through the data/index resolver.
        if isinstance(
            ctx,
            (
                CP.DataNameContext,
                CP.DataDescNameContext,
                CP.ConditionNameContext,
                CP.RecordNameContext,
                CP.CobolWordContext,
            ),
        ):
            return self._create_data_call(ctx)
        # Name-only contexts with no resolution target yet -> UndefinedCall.
        if isinstance(
            ctx,
            (
                CP.AlphabetNameContext,
                CP.AssignmentNameContext,
                CP.ClassNameContext,
                CP.LibraryNameContext,
                CP.LocalNameContext,
                CP.SystemNameContext,
                CP.ProgramNameContext,
            ),
        ):
            return self._create_undefined_call(ctx)
        return self._create_data_call(ctx)

    def _create_identifier_call(self, ctx):
        """Mirror ``createCall(IdentifierContext)``: delegate to the inner ref."""
        from .call import CallDelegate

        inner = None
        if ctx.qualifiedDataName() is not None:
            inner = self.create_call(ctx.qualifiedDataName())
        elif ctx.tableCall() is not None:
            inner = self.create_call(ctx.tableCall())
        elif ctx.functionCall() is not None:
            inner = self.create_call(ctx.functionCall())
        elif ctx.specialRegister() is not None:
            inner = self.create_call(ctx.specialRegister())
        if inner is not None:
            result = CallDelegate(inner, self.program_unit, ctx)
            self._register(result)
            return result
        return self._create_data_call(ctx)

    def _create_qualified_data_name_call(self, ctx):
        """Mirror ``createCall(QualifiedDataNameContext)``."""
        from .call import CallDelegate

        for fmt_attr in (
            "qualifiedDataNameFormat1",
            "qualifiedDataNameFormat2",
            "qualifiedDataNameFormat3",
            "qualifiedDataNameFormat4",
        ):
            fmt = getattr(ctx, fmt_attr, lambda: None)()
            if fmt is not None:
                inner = self.create_call(fmt)
                result = CallDelegate(inner, self.program_unit, ctx)
                self._register(result)
                return result
        return self._create_data_call(ctx)

    def _create_qualified_data_name_format1_call(self, ctx):
        """Mirror ``createCall(QualifiedDataNameFormat1Context)``.

        Resolves an ``A IN B IN C`` qualified reference by walking the candidate
        data-description entry's parent group chain against the (reversed)
        ``qualifiedInData`` list, matching on upper-cased symbol. This is the
        disambiguation that makes IN/OF qualification meaningful.
        """
        qualified_in_data = getattr(ctx, "qualifiedInData", lambda: [])() or []
        if qualified_in_data:
            name = self.determine_name(ctx)
            candidates = self.find_data_description_entries(name)
            parent_ctxs = list(reversed(qualified_in_data))
            valid = None
            for candidate in candidates:
                if self._is_same_in_data(candidate, parent_ctxs):
                    valid = candidate
                    break
            if valid is None:
                return self._create_undefined_call(ctx)
            return self._create_data_call_for(name, valid, ctx)
        if getattr(ctx, "dataName", lambda: None)() is not None:
            return self.create_call(ctx.dataName())
        if getattr(ctx, "conditionName", lambda: None)() is not None:
            return self.create_call(ctx.conditionName())
        return self._create_data_call(ctx)

    def _create_qualified_data_name_format2_call(self, ctx):
        """Mirror ``createCall(QualifiedDataNameFormat2Context)``: paragraph IN section."""
        from .call import ProcedureCall

        name = self.determine_name(ctx)
        in_section = getattr(ctx, "inSection", lambda: None)()
        section_name = self.determine_name(in_section) if in_section is not None else None
        section = self.find_section(section_name)
        if section is None:
            return self._create_undefined_call(ctx)
        paragraph = section.get_paragraph(name)
        if paragraph is None:
            return self._create_undefined_call(ctx)
        result = ProcedureCall(name, paragraph, self.program_unit, ctx)
        self._register(result)
        return result

    def _create_table_call(self, ctx):
        """Mirror ``createCall(TableCallContext)``: subscripted data reference."""
        from .call import Subscript, TableCall

        name = self.determine_name(ctx)
        entries = self.find_data_description_entries(name)
        if not entries:
            return self._create_undefined_call(ctx)
        entry = entries[0]
        table_call = TableCall(name, entry, self.program_unit, ctx)
        entry.add_call(table_call)
        for subscript_ctx in (getattr(ctx, "subscript", lambda: [])() or []):
            subscript = Subscript(self.program_unit, subscript_ctx)
            subscript.value_stmt = self._create_subscript_value_stmt(subscript_ctx)
            table_call.add_subscript(subscript)
        self._register(table_call)
        return table_call

    def _create_subscript_value_stmt(self, ctx):
        # subscript: ALL | integerLiteral | qualifiedDataName integerLiteral?
        #            | indexName integerLiteral? | arithmeticExpression
        for child_attr in ("integerLiteral", "qualifiedDataName", "indexName", "arithmeticExpression"):
            child = getattr(ctx, child_attr, lambda: None)()
            if child is not None:
                return self.create_value_stmt(child)
        return None

    def _create_special_register_call(self, ctx):
        """Mirror ``createCall(SpecialRegisterContext)``: ADDRESS OF, LENGTH OF, ..."""
        from .call import SpecialRegisterCall

        st = SpecialRegisterCall.SpecialRegisterType
        token_to_type = (
            ("ADDRESS", st.ADDRESS_OF),
            ("DATE", st.DATE),
            ("DAY", st.DAY),
            ("DAY_OF_WEEK", st.DAY_OF_WEEK),
            ("DEBUG_CONTENTS", st.DEBUG_CONTENTS),
            ("DEBUG_ITEM", st.DEBUG_ITEM),
            ("DEBUG_LINE", st.DEBUG_LINE),
            ("DEBUG_NAME", st.DEBUG_NAME),
            ("DEBUG_SUB_1", st.DEBUG_SUB_1),
            ("DEBUG_SUB_2", st.DEBUG_SUB_2),
            ("DEBUG_SUB_3", st.DEBUG_SUB_3),
            ("LENGTH", st.LENGTH_OF),
            ("LINAGE_COUNTER", st.LINAGE_COUNTER),
            ("LINE_COUNTER", st.LINE_COUNTER),
            ("PAGE_COUNTER", st.PAGE_COUNTER),
            ("RETURN_CODE", st.RETURN_CODE),
            ("SHIFT_IN", st.SHIFT_IN),
            ("SHIFT_OUT", st.SHIFT_OUT),
            ("SORT_CONTROL", st.SORT_CONTROL),
            ("SORT_CORE_SIZE", st.SORT_CORE_SIZE),
            ("SORT_FILE_SIZE", st.SORT_FILE_SIZE),
            ("SORT_MESSAGE", st.SORT_MESSAGE),
            ("SORT_MODE_SIZE", st.SORT_MODE_SIZE),
            ("SORT_RETURN", st.SORT_RETURN),
            ("TALLY", st.TALLY),
            ("TIME", st.TIME),
            ("WHEN_COMPILED", st.WHEN_COMPILED),
        )
        sr_type = None
        for token_name, t in token_to_type:
            accessor = getattr(ctx, token_name, None)
            if callable(accessor) and accessor() is not None:
                sr_type = t
                break
        result = SpecialRegisterCall(sr_type, self.program_unit, ctx)
        if getattr(ctx, "identifier", lambda: None)() is not None:
            result.set_identifier_call(self.create_call(ctx.identifier()))
        self._register(result)
        return result

    def _create_function_call(self, ctx):
        """Mirror ``createCall(FunctionCallContext)``."""
        from .call import FunctionCall

        result = FunctionCall(self.determine_name(ctx), self.program_unit, ctx)
        self._register(result)
        return result

    def _create_mnemonic_call(self, ctx):
        """Mirror ``createCall(MnemonicNameContext)``."""
        from .call import MnemonicCall

        result = MnemonicCall(self.determine_name(ctx), self.program_unit, ctx)
        self._register(result)
        return result

    def _create_environment_call(self, ctx):
        """Mirror ``createCall(EnvironmentNameContext)``."""
        from .call import EnvironmentCall

        result = EnvironmentCall(self.determine_name(ctx), self.program_unit, ctx)
        self._register(result)
        return result

    def _create_report_call(self, ctx):
        """Mirror ``createCall(ReportNameContext)``."""
        from .call import ReportCall

        name = self.determine_name(ctx)
        report = self.find_report_description(name)
        if report is None:
            return self._create_undefined_call(ctx)
        result = ReportCall(name, report, self.program_unit, ctx)
        self._register(result)
        return result

    def _create_cd_name_call(self, ctx):
        """Mirror ``createCall(CdNameContext)``."""
        from .call import CommunicationDescriptionEntryCall

        name = self.determine_name(ctx)
        entry = self.find_communication_description_entry(name)
        if entry is None:
            return self._create_undefined_call(ctx)
        result = CommunicationDescriptionEntryCall(name, entry, self.program_unit, ctx)
        entry.add_call(result)
        self._register(result)
        return result

    def _create_undefined_call(self, ctx):
        from .call import UndefinedCall

        result = UndefinedCall(self.determine_name(ctx), self.program_unit, ctx)
        self._register(result)
        return result

    def _create_file_control_call(self, ctx):
        """Resolve a file-name reference to a :class:`FileControlEntryCall`.

        Mirrors ``ProgramUnitElementImpl.createCall(FileNameContext)``: if the
        name matches a SELECT entry, link a FileControlEntryCall; otherwise fall
        back to a data-description call (as proleap does).
        """
        existing = self._get_element(ctx)
        if existing is not None:
            return existing
        name = self.determine_name(ctx)
        fce = self.find_file_control_entry(name)
        if fce is not None:
            from .call import FileControlEntryCall

            result = FileControlEntryCall(name, fce, self.program_unit, ctx)
            fce.add_call(result)
            self._register(result)
            return result
        return self._create_data_call(ctx)

    def _create_data_call(self, ctx: ParserRuleContext):
        """Resolve a data reference, checking index names first.

        Mirrors ``ProgramUnitElementImpl.createDataDescriptionEntryCall``: an
        index name (from OCCURS INDEXED BY) resolves to :class:`IndexCall`;
        otherwise the data-division sections are searched and a
        :class:`DataDescriptionEntryCall` is linked; otherwise
        :class:`UndefinedCall`.
        """
        existing = self._get_element(ctx)
        if existing is not None:
            return existing
        name = self.determine_name(ctx)
        index = self.find_index(name)
        if index is not None:
            from .call import IndexCall

            result = IndexCall(index, self.program_unit, ctx)
            self._register(result)
            return result
        entries = self.find_data_description_entries(name)
        if entries:
            return self._create_data_call_for(name, entries[0], ctx)
        return self._create_undefined_call(ctx)

    def _create_data_call_for(self, name, entry, ctx: ParserRuleContext):
        """Link a resolved :class:`DataDescriptionEntryCall` to ``entry``."""
        from .call import DataDescriptionEntryCall

        existing = self._get_element(ctx)
        if existing is not None:
            return existing
        result = DataDescriptionEntryCall(name, entry, self.program_unit, ctx)
        entry.add_call(result)
        self._register(result)
        return result

    def _create_procedure_name_call(self, ctx):
        from .call import ProcedureCall, SectionCall, UndefinedCall

        name = self.determine_name(ctx)
        in_section = getattr(ctx, "inSection", lambda: None)()
        if in_section is None:
            paragraph = self.find_paragraph(name)
            section = self.find_section(name)
            if paragraph is not None:
                result = ProcedureCall(name, paragraph, self.program_unit, ctx)
            elif section is not None:
                result = SectionCall(name, section, self.program_unit, ctx)
            else:
                result = UndefinedCall(name, self.program_unit, ctx)
        else:
            section_name = self.determine_name(in_section)
            section = self.find_section(section_name)
            if section is None:
                result = UndefinedCall(name, self.program_unit, ctx)
            else:
                paragraph = section.get_paragraph(name)
                if paragraph is None:
                    result = UndefinedCall(name, self.program_unit, ctx)
                else:
                    result = ProcedureCall(name, paragraph, self.program_unit, ctx)

        self._register(result)
        return result

    # -- qualified-data / index resolution helpers ---------------------------

    def _is_same_in_data(self, candidate, parent_in_data_ctxs) -> bool:
        """Mirror ``ProgramUnitElementImpl.isSameInData``.

        Walks the candidate's parent-group chain against the (already-reversed)
        ``qualifiedInData`` list, matching on upper-cased symbol. Returns True
        iff every qualifier matches an ancestor group in order.
        """
        current_parent = getattr(candidate, "parent_data_description_entry_group", None)
        for parent_ctx in parent_in_data_ctxs:
            if current_parent is None:
                return False
            current_symbol = _symbol(getattr(current_parent, "name", None))
            parent_symbol = _symbol(self.determine_name(parent_ctx))
            if not current_symbol or current_symbol != parent_symbol:
                return False
            current_parent = getattr(current_parent, "parent_data_description_entry_group", None)
        return True

    def find_index(self, name: Optional[str]):
        """Mirror ``ProgramUnitElementImpl.findIndex``.

        Scans working-storage group entries' OCCURS INDEXED BY clauses for an
        index of this name. Returns None until OCCURS clauses are captured.
        """
        if name is None:
            return None
        sym = name.upper()
        dd = self.program_unit.data_division
        if dd is None or dd.working_storage_section is None:
            return None
        from .data import DataDescriptionEntry

        for entry in dd.working_storage_section.data_description_entries:
            if entry.data_description_entry_type != DataDescriptionEntry.Type.GROUP:
                continue
            for occurs in getattr(entry, "occurs_clauses", None) or []:
                indexed = getattr(occurs, "occurs_indexed", None)
                if indexed is None:
                    continue
                index = indexed.get_index(sym)
                if index is not None:
                    return index
        return None

    def find_report_description(self, name: Optional[str]):
        # Report section is not yet modeled (Phase D2); resolve to None so
        # ReportName references become UndefinedCall, matching Java when no
        # report description exists.
        return None

    def find_communication_description_entry(self, name: Optional[str]):
        # Communication CD-level entries are not yet modeled; resolve to None.
        return None

    # -- literals ------------------------------------------------------------

    def create_integer_literal(self, ctx):
        from .literal import IntegerLiteral

        result = self._get_element(ctx)
        if result is None:
            from .util_string import parse_decimal  # local helper, see below

            result = IntegerLiteral(parse_decimal(ctx.getText()), self.program_unit, ctx)
            self._register(result)
        return result

    def create_numeric_literal(self, ctx):
        from .literal import NumericLiteral

        result = self._get_element(ctx)
        if result is None:
            result = NumericLiteral(self.program_unit, ctx)
            if ctx.integerLiteral() is not None:
                from .util_string import parse_decimal

                result.value = parse_decimal(ctx.getText())
                result.numeric_literal_type = NumericLiteral.Type.INTEGER
            elif self._has_token(ctx, "ZERO"):
                result.value = parse_decimal("0")
                result.numeric_literal_type = NumericLiteral.Type.INTEGER
            elif ctx.NUMERICLITERAL() is not None:
                from .util_string import parse_decimal

                result.value = parse_decimal(ctx.NUMERICLITERAL().getText())
                result.numeric_literal_type = NumericLiteral.Type.FLOAT
            self._register(result)
        return result

    def create_boolean_literal(self, ctx):
        from .literal import BooleanLiteral

        result = self._get_element(ctx)
        if result is None:
            result = BooleanLiteral(self._parse_bool(ctx.getText()), self.program_unit, ctx)
            self._register(result)
        return result

    def create_figurative_constant(self, ctx):
        from .literal import FigurativeConstant, Literal

        result = self._get_element(ctx)
        if result is None:
            fc_type = self._figurative_type(ctx)
            result = FigurativeConstant(fc_type, self.program_unit, ctx)
            if ctx.literal() is not None:
                result.literal = self.create_literal(ctx.literal())
            self._register(result)
        return result

    def create_literal(self, ctx):
        from .literal import Literal

        result = self._get_element(ctx)
        if result is None:
            result = Literal(self.program_unit, ctx)
            text = ctx.getText()
            if ctx.NONNUMERICLITERAL() is not None:
                result.non_numeric_literal = text[1:-1] if text.startswith("'") or text.startswith('"') else text
                result.literal_type = Literal.Type.NON_NUMERIC
            elif ctx.numericLiteral() is not None:
                result.numeric_literal = self.create_numeric_literal(ctx.numericLiteral())
                result.literal_type = Literal.Type.NUMERIC
            elif ctx.booleanLiteral() is not None:
                result.boolean_literal = self.create_boolean_literal(ctx.booleanLiteral())
                result.literal_type = Literal.Type.BOOLEAN
            elif ctx.figurativeConstant() is not None:
                result.figurative_constant = self.create_figurative_constant(ctx.figurativeConstant())
                result.literal_type = Literal.Type.FIGURATIVE_CONSTANT
            self._register(result)
        return result

    # -- value statements ----------------------------------------------------

    def create_value_stmt(self, *ctxs):
        """Build the :class:`ValueStmt` for the first non-null ctx given.

        Mirrors ``ProgramUnitElementImpl.createValueStmt(ParserRuleContext...)``.
        """
        for ctx in ctxs:
            if ctx is None:
                continue
            return self._create_value_stmt_one(ctx)
        return None

    def _create_value_stmt_one(self, ctx):
        from ..CobolParser import CobolParser as CP
        from .valuestmt import (
            ArithmeticValueStmt,
            CallValueStmt,
            ConditionValueStmt,
            IntegerLiteralValueStmt,
            LiteralValueStmt,
        )

        if isinstance(ctx, CP.LiteralContext):
            result = LiteralValueStmt(self.program_unit, ctx)
            result.literal = self.create_literal(ctx)
            return result
        if isinstance(ctx, CP.IntegerLiteralContext):
            result = IntegerLiteralValueStmt(self.program_unit, ctx)
            result.integer_literal = self.create_integer_literal(ctx)
            return result
        if isinstance(ctx, CP.ConditionContext):
            return self.create_condition_value_stmt(ctx)
        if isinstance(ctx, CP.ArithmeticExpressionContext):
            return self.create_arithmetic_value_stmt(ctx)
        call = self.create_call(ctx)
        if call is None:
            return None
        return CallValueStmt(call, self.program_unit, ctx)

    def create_condition_value_stmt(self, ctx):
        from .valuestmt import ConditionValueStmt

        result = self._get_element(ctx)
        if result is None:
            # Full combinable/and-or decomposition deferred; retain ctx.
            result = ConditionValueStmt(self.program_unit, ctx)
            self._register(result)
        return result

    def create_arithmetic_value_stmt(self, ctx):
        from .valuestmt import ArithmeticValueStmt

        result = self._get_element(ctx)
        if result is None:
            # Full mult-divs/plus-minus decomposition deferred; retain ctx.
            result = ArithmeticValueStmt(self.program_unit, ctx)
            self._register(result)
        return result

    # -- small parsing helpers (port of AsgStringUtils) ----------------------

    @staticmethod
    def _has_token(ctx, token_text: str) -> bool:
        return token_text.upper() in ctx.getText().upper()

    @staticmethod
    def _parse_bool(text: str) -> Optional[bool]:
        upper = text.upper()
        if "TRUE" in upper:
            return True
        if "FALSE" in upper:
            return False
        return None

    @staticmethod
    def _figurative_type(ctx):
        from .literal import FigurativeConstant

        text = ctx.getText().upper()
        # Match the longest token form first so "LOW-VALUES" does not collapse
        # to "LOW-VALUE", "HIGH-VALUES" to "HIGH-VALUE", etc. Java dispatches on
        # the exact figurative token; substring-matching by enum-declaration
        # order (LOW_VALUE before LOW_VALUES) would misclassify the plural forms.
        candidates = sorted(FigurativeConstant.Type, key=lambda m: len(m.name), reverse=True)
        for member in candidates:
            token = member.name.replace("_", "-")
            if token in text:
                return member
        return None
