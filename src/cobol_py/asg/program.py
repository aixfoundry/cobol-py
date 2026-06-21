"""Top-level ASG containers: Program, CompilationUnit, ProgramUnit.

Ports ``metamodel/impl/{Program,CompilationUnit,ProgramUnit}Impl`` (interface +
impl collapsed). ProgramUnit owns the four COBOL divisions; identification and
procedure are the real Phase B implementations (imported), environment and data
remain minimal stubs until Phases D/E.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from antlr4.CommonTokenStream import CommonTokenStream
from antlr4.ParserRuleContext import ParserRuleContext

from .base import ASGElement, CobolDivisionElement, CompilationUnitElement, NamedElement
from .data import DataDivision
from .environment import EnvironmentDivision
from .identification import IdentificationDivision
from .procedure.division import ProcedureDivision
from .registry import ASGElementRegistry


class Program(ASGElement):
    """Root of the ASG: holds the registry and the compilation units."""

    def __init__(self) -> None:
        super().__init__(program=None, ctx=None)
        self._registry = ASGElementRegistry()
        self._compilation_units: "Dict[str, CompilationUnit]" = {}

    @property
    def registry(self) -> ASGElementRegistry:
        return self._registry

    def register_compilation_unit(self, compilation_unit: "CompilationUnit") -> None:
        key = (compilation_unit.name or "").lower()
        self._compilation_units[key] = compilation_unit

    @property
    def compilation_units(self) -> "List[CompilationUnit]":
        return list(self._compilation_units.values())

    @property
    def compilation_unit(self) -> "Optional[CompilationUnit]":
        units = self.compilation_units
        return units[0] if units else None

    def get_compilation_unit(self, name: str) -> "Optional[CompilationUnit]":
        return self._compilation_units.get((name or "").lower())


class CompilationUnit(ASGElement, NamedElement):
    """One source file's contribution: a name, its tokens/lines, program units."""

    def __init__(
        self,
        name: str,
        program: Program,
        tokens: CommonTokenStream,
        ctx: ParserRuleContext,
    ) -> None:
        super().__init__(program=program, ctx=ctx)
        self.name = name
        self.tokens = tokens
        self.lines: List[str] = []
        self._filler_counter = 0
        self._program_units: "List[ProgramUnit]" = []
        self._register(self)
        program.register_compilation_unit(self)

    def add_program_unit(self, ctx: ParserRuleContext) -> "ProgramUnit":
        result = self._get_element(ctx)
        if result is None:
            result = ProgramUnit(self, ctx)
            self._register(result)
            self._program_units.append(result)
        return result  # type: ignore[return-value]

    @property
    def program_units(self) -> "List[ProgramUnit]":
        return self._program_units

    @property
    def program_unit(self) -> "Optional[ProgramUnit]":
        units = self._program_units
        return units[0] if units else None

    def increment_filler_counter(self) -> int:
        current = self._filler_counter
        self._filler_counter += 1
        return current

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"CompilationUnit(name={self.name!r})"


class ProgramUnit(CompilationUnitElement):
    """A program unit: the four COBOL divisions."""

    def __init__(self, compilation_unit: CompilationUnit, ctx: ParserRuleContext) -> None:
        super().__init__(compilation_unit=compilation_unit, ctx=ctx)
        self.identification_division: Optional[IdentificationDivision] = None
        self.environment_division: Optional[EnvironmentDivision] = None
        self.data_division: Optional[DataDivision] = None
        self.procedure_division: Optional[ProcedureDivision] = None

    def _add_division(self, cls, ctx):  # type: ignore[no-untyped-def]
        result = self._get_element(ctx)
        if result is None:
            result = cls(self, ctx)
            self._register(result)
        return result

    def add_identification_division(self, ctx) -> IdentificationDivision:
        result = self._add_division(IdentificationDivision, ctx)
        # Parse PROGRAM-ID (Phase B). Optional body paragraphs (author, date, ...)
        # are deferred. Mirrors ProgramUnitImpl.addIdentificationDivision.
        program_id_ctx = ctx.programIdParagraph()
        if program_id_ctx is not None:
            result.add_program_id_paragraph(program_id_ctx)
        self.identification_division = result
        return result

    def add_environment_division(self, ctx) -> EnvironmentDivision:
        result = self._add_division(EnvironmentDivision, ctx)
        # Parse the body inline (configuration / input-output / special-names),
        # mirroring EnvironmentDivisionImpl. File-control entries are built here,
        # in pass 1, so file-name references resolve during the statement pass.
        for body_ctx in ctx.environmentDivisionBody():
            if body_ctx.configurationSection() is not None:
                result.add_configuration_section(body_ctx.configurationSection())
            elif body_ctx.inputOutputSection() is not None:
                result.add_input_output_section(body_ctx.inputOutputSection())
            elif body_ctx.specialNamesParagraph() is not None:
                result.add_special_names_paragraph(body_ctx.specialNamesParagraph())
        self.environment_division = result
        return result

    def add_data_division(self, ctx) -> "DataDivision":
        self.data_division = self._add_division(DataDivision, ctx)
        return self.data_division

    def add_procedure_division(self, ctx) -> ProcedureDivision:
        self.procedure_division = self._add_division(ProcedureDivision, ctx)
        return self.procedure_division

# All four divisions (Identification, Environment, Data, Procedure) are now
# real implementations imported above; no stubs remain.
