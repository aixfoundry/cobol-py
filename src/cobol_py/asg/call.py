"""Call metamodel: resolved references to declarations.

Ports ``metamodel/call`` (interface + impl collapsed). A :class:`Call` is a
reference from a statement to a declared element (paragraph, section, data
item, ...). :class:`CallDelegate` wraps another call (e.g. an identifier that
delegates to its qualified-data-name call); ``unwrap`` peels delegates.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Optional

from antlr4.ParserRuleContext import ParserRuleContext

from .base import CobolDivisionElement, NamedElement


class CallTypeEnum(Enum):
    COMMUNICATION_DESCRIPTION_ENTRY_CALL = "COMMUNICATION_DESCRIPTION_ENTRY_CALL"
    DATA_DESCRIPTION_ENTRY_CALL = "DATA_DESCRIPTION_ENTRY_CALL"
    ENVIRONMENT_CALL = "ENVIRONMENT_CALL"
    FILE_CONTROL_ENTRY_CALL = "FILE_CONTROL_ENTRY_CALL"
    FUNCTION_CALL = "FUNCTION_CALL"
    INDEX_CALL = "INDEX_CALL"
    MNEMONIC_CALL = "MNEMONIC_CALL"
    PROCEDURE_CALL = "PROCEDURE_CALL"
    REPORT_DESCRIPTION_CALL = "REPORT_DESCRIPTION_CALL"
    REPORT_DESCRIPTION_ENTRY_CALL = "REPORT_DESCRIPTION_ENTRY_CALL"
    SCREEN_DESCRIPTION_ENTRY_CALL = "SCREEN_DESCRIPTION_ENTRY_CALL"
    SECTION_CALL = "SECTION_CALL"
    SPECIAL_REGISTER_CALL = "SPECIAL_REGISTER_CALL"
    TABLE_CALL = "TABLE_CALL"
    UNDEFINED_CALL = "UNDEFINED_CALL"


class Call(CobolDivisionElement, NamedElement):
    """Base for all calls. Subclasses set ``call_type`` and ``name``."""

    call_type: Optional[CallTypeEnum] = None

    def unwrap(self) -> "Call":
        return self


class _NamedCall(Call):
    """A call identified by a name string (mirrors ``CallImpl``)."""

    def __init__(self, name: Optional[str], program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name


class ProcedureCall(_NamedCall):
    """A call to a paragraph."""

    call_type = CallTypeEnum.PROCEDURE_CALL

    def __init__(self, name, paragraph, program_unit, ctx) -> None:
        super().__init__(name, program_unit, ctx)
        self.paragraph = paragraph


class SectionCall(_NamedCall):
    """A call to a section."""

    call_type = CallTypeEnum.SECTION_CALL

    def __init__(self, name, section, program_unit, ctx) -> None:
        super().__init__(name, program_unit, ctx)
        self.section = section


class DataDescriptionEntryCall(_NamedCall):
    """A call to a data-description entry (resolved in Phase D)."""

    call_type = CallTypeEnum.DATA_DESCRIPTION_ENTRY_CALL

    def __init__(self, name, data_description_entry, program_unit, ctx) -> None:
        super().__init__(name, program_unit, ctx)
        self.data_description_entry = data_description_entry


class UndefinedCall(_NamedCall):
    """A call whose target could not be resolved."""

    call_type = CallTypeEnum.UNDEFINED_CALL


class CallDelegate(Call):
    """A call that delegates to another call (mirrors ``CallDelegateImpl``)."""

    def __init__(self, delegate: Call, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.delegate = delegate
        self.call_type = delegate.call_type if delegate is not None else None
        self.name = delegate.name if delegate is not None else None

    def unwrap(self) -> "Call":
        return self.delegate.unwrap() if self.delegate is not None else self
