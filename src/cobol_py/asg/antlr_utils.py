"""AST-tree navigation helpers for the ASG.

Ports ``io.proleap.cobol.asg.util.ANTLRUtils``. The ASG is layered on the AST:
each :class:`ASGElement` retains its ANTLR ``ctx``, and navigation walks the
``ctx`` parse-tree (up to the parent, down to children) consulting the
:class:`~cobol_py.asg.registry.ASGElementRegistry` to map ``ctx`` nodes back to
ASG elements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Type, TypeVar

if TYPE_CHECKING:
    from antlr4.tree.Tree import ParseTree

    from .base import ASGElement
    from .registry import ASGElementRegistry

T = TypeVar("T", bound="ASGElement")


def _children(ctx: "ParseTree") -> "List[ParseTree]":
    """Immediate parse-tree children of ``ctx`` (empty for leaves)."""
    if ctx is None:
        return []
    count = ctx.getChildCount()
    return [ctx.getChild(i) for i in range(count)]


def find_parent(
    asg_type: Type[T], from_ctx: "Optional[ParseTree]", registry: "ASGElementRegistry"
) -> Optional[T]:
    """Walk up the ``ctx`` tree from ``from_ctx`` and return the first
    registered ASG element that is an instance of ``asg_type``.

    Mirrors ``ANTLRUtils.findParent``. ``type.isAssignableFrom`` becomes
    :func:`isinstance`.
    """
    current = from_ctx
    while current is not None:
        # Python ANTLR target exposes the parent as ``parentCtx`` (an
        # attribute), not via the Java ``getParent()`` method.
        current = getattr(current, "parentCtx", None)
        element = registry.get(current)
        if element is not None and isinstance(element, asg_type):
            return element  # type: ignore[return-value]
    return None


def find_children(
    asg_type: Type[T], ctx: "Optional[ParseTree]", registry: "ASGElementRegistry"
) -> List[T]:
    """Return the immediate registered ASG children of ``ctx`` that are
    instances of ``asg_type``."""
    result: List[T] = []
    for child in _children(ctx):
        element = registry.get(child)
        if element is not None and isinstance(element, asg_type):
            result.append(element)  # type: ignore[arg-type]
    return result


def find_asg_element_children(
    ctx: "Optional[ParseTree]", registry: "ASGElementRegistry"
) -> "List[ASGElement]":
    """All immediate registered ASG children of ``ctx``."""
    # Lazy import: base.py imports this module, so we cannot import ASGElement
    # at module load without creating a cycle.
    from .base import ASGElement

    return find_children(ASGElement, ctx, registry)


def find_ancestors(
    asg_type: Type[T], from_ctx: "Optional[ParseTree]", registry: "ASGElementRegistry"
) -> List[T]:
    """Every ancestor ASG element of ``from_ctx`` of type ``asg_type``.

    Mirrors ``ANTLRUtils.findAncestors``: keeps walking up through each found
    parent's ``ctx``.
    """
    result: List[T] = []
    current = from_ctx
    while current is not None:
        parent = find_parent(asg_type, current, registry)
        if parent is None:
            break
        result.append(parent)
        current = parent.ctx
    return result
