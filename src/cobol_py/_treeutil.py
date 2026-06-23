"""Parse-tree comparison helpers (port of proleap test utils).

``clean_file_tree`` ports ``io.proleap.cobol.util.CobolTestStringUtils.cleanFileTree``
and ``format_for`` mirrors the directory-name convention proleap's
``TestGenerator.getCobolSourceFormat`` uses. Shared by the golden test
``tests/test_ast_tree.py`` and the consistency harness
``scripts/dump_parse_trees.py`` so both apply byte-identical normalisation.

``format_tree`` produces an indented, human-readable tree representation
from an ANTLR parse-tree node, suitable for saving as a ``.tree`` file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from antlr4.ParserRuleContext import ParserRuleContext

from . import CobolSourceFormatEnum


def clean_file_tree(value: str) -> str:
    """Port of ``CobolTestStringUtils.cleanFileTree``.

    Strips escaped/literal newlines and collapses all remaining whitespace
    (including the space before a closing paren) so the comparison ignores
    incidental whitespace differences between the Java and Python tree dumps.
    """
    value = value.replace("\\r", "").replace("\\n", "")
    value = value.replace("\r", "").replace("\n", "")
    value = re.sub(r"[\s]+", " ", value)
    value = re.sub(r"[\s]+\)", ")", value)
    return value


def format_for(path: Path) -> CobolSourceFormatEnum:
    """Infer the COBOL source format from the file's directory.

    Mirrors proleap's ``TestGenerator.getCobolSourceFormat``: a path segment
    ``tandem`` / ``variable`` selects that format, otherwise FIXED.
    """
    name = path.as_posix()
    if "/tandem/" in name:
        return CobolSourceFormatEnum.TANDEM
    if "/variable/" in name:
        return CobolSourceFormatEnum.VARIABLE
    return CobolSourceFormatEnum.FIXED


def format_tree(tree: ParserRuleContext, parser) -> str:
    """Produce a multi-line, tab-indented tree in Java ``Trees.toStringTree`` format.

    Mirrors ANTLR4 Java's ``Trees.toStringTree(Tree, Parser)`` exactly:
    rule nodes with children are wrapped in ``(ruleName ...)``; child rules
    with children start on a new line with a leading tab per depth; terminal
    tokens and childless rules stay inline.
    """
    return _to_string_tree_java(tree, parser.ruleNames, 0) + "\n"


def _to_string_tree_java(node, rule_names: list[str], depth: int) -> str:
    """Recursive core matching Java ANTLR4 Trees.toStringTree multi-line layout."""
    rule_idx: int = node.getRuleIndex() if hasattr(node, "getRuleIndex") else -1
    child_count: int = node.getChildCount()

    # Terminal node
    if rule_idx < 0:
        text: str = node.getText() if hasattr(node, "getText") else str(node)
        return _escape_ws(text)

    # Rule node — no children → bare name (no parens)
    if child_count == 0:
        return rule_names[rule_idx]

    # Rule node with children → (ruleName child1 child2 ... )
    indent = "\t" * depth
    parts: list[str] = [f"({rule_names[rule_idx]}"]
    for i in range(child_count):
        child = node.getChild(i)
        child_str = _to_string_tree_java(child, rule_names, depth + 1)
        child_is_rule = (
            hasattr(child, "getRuleIndex")
            and child.getRuleIndex() >= 0
            and child.getChildCount() > 0
        )
        if child_is_rule:
            parts.append(f"\n{indent}\t{child_str}")
        else:
            parts.append(f" {child_str}")
    parts.append(")")
    return "".join(parts)


def _escape_ws(s: str) -> str:
    """Escape whitespace for ANTLR tree output (match Java Utils.escapeWhitespace)."""
    return s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
