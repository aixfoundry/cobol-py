"""Patch the ANTLR4 Python runtime to cap recursion depth in ATN closure.

Two COBOL-85 NIST programs (NC207A, NC246A) trigger exponential recursion
in the ``closure`` / ``closure_`` methods of ``ParserATNSimulator`` when the
grammar's deeply-nested ``qualifiedDataName`` chains (up to 49 levels of
``OF`` qualification) combine with OCCURS subscript paths. The recursion
expands the ATN config set without bound, exhausting Python's call stack or
running out of memory.

This module monkey-patches ``closure_`` to enforce a maximum recursion
depth. When exceeded, the recursive call is skipped — which is safe because
the skipped paths represent deeply-nested epsilon transitions through rule
stop states that would not contribute to a viable parse anyway.

Usage (applied automatically by ``_start_rule_two_stage``)::

    from cobol_py._antlr_patch import patch_context
    with patch_context(max_closure_depth=500):
        parser.startRule()
"""

from __future__ import annotations

import contextlib
import logging

_LOG = logging.getLogger(__name__)

DEFAULT_MAX_CLOSURE_DEPTH = 500

_original_closure_ = None
_max_depth = DEFAULT_MAX_CLOSURE_DEPTH


def _patched_closure_(
    self, config, configs, closureBusy, collectPredicates,
    fullCtx, depth, treatEofAsEpsilon,
):
    """Depth-capped ``closure_`` — identical to original but skips further
    recursion once *depth* exceeds ``_max_depth``."""
    if depth > _max_depth:
        return
    return _original_closure_(
        self, config, configs, closureBusy, collectPredicates,
        fullCtx, depth, treatEofAsEpsilon,
    )


def apply_closure_patch(max_depth=None):
    """Replace ``ParserATNSimulator.closure_`` with the depth-capped version."""
    import antlr4.atn.ParserATNSimulator as _mod

    global _original_closure_, _max_depth

    if max_depth is not None:
        _max_depth = max_depth

    if _original_closure_ is None:
        _original_closure_ = _mod.ParserATNSimulator.closure_
        _mod.ParserATNSimulator.closure_ = _patched_closure_
        _LOG.info("ANTLR closure depth cap applied (max_depth=%d)", _max_depth)


def remove_closure_patch():
    """Restore the original ``closure_``."""
    import antlr4.atn.ParserATNSimulator as _mod

    global _original_closure_
    if _original_closure_ is not None:
        _mod.ParserATNSimulator.closure_ = _original_closure_
        _original_closure_ = None
        _LOG.info("ANTLR closure depth cap removed")


@contextlib.contextmanager
def patch_context(max_closure_depth=None):
    """Context manager that applies the closure depth cap for one parse."""
    apply_closure_patch(max_closure_depth)
    try:
        yield
    finally:
        remove_closure_patch()
