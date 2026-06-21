"""ASG element registry.

Ports ``io.proleap.cobol.asg.metamodel.registry`` (interface + impl collapse to
one class). The registry is the backbone of the ASG: a single mapping from an
ANTLR parse-tree node (``ctx``) to the :class:`ASGElement` built from it. This
lets any element navigate to its parent/children by walking the AST ``ctx``
tree (see :mod:`cobol_py.asg.antlr_utils`) and lets ``add_*`` factories avoid
building the same element twice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from antlr4.tree.Tree import ParseTree

    from .base import ASGElement


class ASGElementRegistry:
    """Maps an ANTLR ``ctx`` to the :class:`ASGElement` created from it.

    Mirrors ``ASGElementRegistryImpl``: a ``dict[ParseTree, ASGElement]``.
    ANTLR ``ParserRuleContext`` objects are identity-hashable, so they key a
    Python dict exactly as they key the Java ``HashMap``.
    """

    def __init__(self) -> None:
        self._elements: "Dict[ParseTree, ASGElement]" = {}

    def add(self, asg_element: "ASGElement") -> None:
        """Register ``asg_element`` keyed by its ``ctx``.

        Mirrors the Java asserts: an element must have a non-null ``ctx`` and
        the same ``ctx`` must not already be registered.
        """
        assert asg_element is not None
        ctx = asg_element.ctx
        assert ctx is not None
        assert ctx not in self._elements
        self._elements[ctx] = asg_element

    def get(self, ctx: "Optional[ParseTree]") -> "Optional[ASGElement]":
        """Return the element registered for ``ctx``, or ``None``."""
        if ctx is None:
            return None
        return self._elements.get(ctx)
