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

        Mirrors ``ProgramUnitElementImpl.createCall(ParserRuleContext...)``:
        dispatches on the runtime ctx type. Data references resolve to
        :class:`UndefinedCall` until the data division exists (Phase D);
        procedure references resolve to paragraphs/sections (built in Phase B).
        """
        if ctx is None:
            return None
        existing = self._get_element(ctx)
        if existing is not None:
            return existing

        from ..CobolParser import CobolParser as CP
        from .call import CallDelegate, UndefinedCall

        if isinstance(ctx, CP.ProcedureNameContext):
            return self._create_procedure_name_call(ctx)
        if isinstance(ctx, CP.FileNameContext):
            return self._create_file_control_call(ctx)
        if isinstance(ctx, CP.IdentifierContext):
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
        return self._create_data_call(ctx)

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
        """Resolve a data reference to a :class:`DataDescriptionEntryCall`.

        Mirrors ``ProgramUnitElementImpl.createDataDescriptionEntryCall``: looks
        up the name across the data-division sections; if found, links a
        :class:`DataDescriptionEntryCall` back to the entry, otherwise falls
        back to :class:`UndefinedCall`.
        """
        from .call import DataDescriptionEntryCall, UndefinedCall

        existing = self._get_element(ctx)
        if existing is not None:
            return existing
        name = self.determine_name(ctx)
        entries = self.find_data_description_entries(name)
        if entries:
            entry = entries[0]
            result = DataDescriptionEntryCall(name, entry, self.program_unit, ctx)
            entry.add_call(result)
        else:
            result = UndefinedCall(name, self.program_unit, ctx)
        self._register(result)
        return result

    def _create_procedure_name_call(self, ctx):
        from .call import ProcedureCall, SectionCall, UndefinedCall

        existing = self._get_element(ctx)
        if existing is not None:
            return existing

        name = self.determine_name(ctx)
        in_section = ctx.inSection()
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
        for member in FigurativeConstant.Type:
            # Match the longest token form present (e.g. HIGH-VALUES vs HIGH-VALUE).
            token = member.name.replace("_", "-")
            if token in text:
                return member
        return None
