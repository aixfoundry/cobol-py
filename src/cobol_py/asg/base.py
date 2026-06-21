"""Base types for the ASG metamodel.

Ports the ``io.proleap.cobol.asg.metamodel`` base interfaces plus the
``metamodel.impl`` base classes, collapsing each Java interface+Impl pair into
one Python class (per the port convention — see ``params.py``).

Inheritance spine (mirrors proleap)::

    ASGElement                         (ctx, program, registry navigation)
    └── CompilationUnitElement         (+ compilation_unit)
        └── ProgramUnitElement         (+ program_unit; hosts create_call /
                                         create_value_stmt in later phases)
            └── CobolDivisionElement   (divisions + statements)

``NamedElement`` / ``Declaration`` are marker bases for elements with a name.
"""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, List, Optional

from antlr4.ParserRuleContext import ParserRuleContext

from . import antlr_utils
from .factory import ProcedureUnitFactory
from .registry import ASGElementRegistry

if TYPE_CHECKING:
    from antlr4.tree.Tree import ParseTree

    from .program import CompilationUnit, Program, ProgramUnit


class ASGElement(ABC):
    """An ASG element corresponding to one AST node.

    Mirrors ``ASGElementImpl``: holds the originating ``ctx`` and a back
    reference to the :class:`Program` (the registry anchor). ``children`` and
    ``parent`` are derived by walking the ``ctx`` tree through the registry.
    """

    def __init__(self, program: "Optional[Program]", ctx: Optional[ParserRuleContext]) -> None:
        self.program = program
        self.ctx = ctx

    @property
    def registry(self) -> ASGElementRegistry:
        """The program-level element registry."""
        return self.program.registry  # type: ignore[union-attr]

    @property
    def children(self) -> "List[ASGElement]":
        """Registered ASG elements among the immediate ``ctx`` children."""
        if self.program is None:
            return []
        return antlr_utils.find_asg_element_children(self.ctx, self.registry)

    @property
    def parent(self) -> "Optional[ASGElement]":
        """The registered ASG element whose ``ctx`` encloses this one."""
        if self.program is None:
            return None
        return antlr_utils.find_parent(ASGElement, self.ctx, self.registry)

    # -- registry helpers (mirror getASGElement / registerASGElement) --------

    def _get_element(self, ctx: "Optional[ParseTree]") -> "Optional[ASGElement]":
        return self.registry.get(ctx)

    def _register(self, element: "ASGElement") -> None:
        self.registry.add(element)

    def determine_name(self, ctx: Optional[ParserRuleContext]) -> Optional[str]:
        """Resolve a display name for ``ctx`` via the name resolver."""
        from .resolver import determine_name

        return determine_name(ctx)


class NamedElement(ABC):
    """Marker base for elements that carry a name (``.name``)."""

    name: Optional[str]


class Declaration(NamedElement):
    """A named declaration (section, paragraph, data description, ...)."""


class CompilationUnitElement(ASGElement):
    """An element that lives within a :class:`CompilationUnit`."""

    def __init__(
        self, compilation_unit: "CompilationUnit", ctx: Optional[ParserRuleContext]
    ) -> None:
        super().__init__(compilation_unit.program, ctx)
        self.compilation_unit = compilation_unit


class ProgramUnitElement(CompilationUnitElement, ProcedureUnitFactory):
    """An element that lives within a :class:`ProgramUnit`.

    This is the base for divisions and statements. It inherits the
    ``create_call`` / ``create_value_stmt`` / ``create_*literal`` factories
    (porting ``ProgramUnitElementImpl``) via :class:`ProcedureUnitFactory`, so
    every statement and clause can build references and operands relative to
    its program unit.
    """

    def __init__(self, program_unit: "ProgramUnit", ctx: Optional[ParserRuleContext]) -> None:
        super().__init__(program_unit.compilation_unit, ctx)
        self.program_unit = program_unit


class CobolDivisionElement(ProgramUnitElement):
    """Base for the four COBOL divisions and for procedure statements."""
