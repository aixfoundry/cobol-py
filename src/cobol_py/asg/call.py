"""Call metamodel: resolved references to declarations.

Ports ``metamodel/call`` (interface + impl collapsed). A :class:`Call` is a
reference from a statement to a declared element (paragraph, section, data
item, ...). :class:`CallDelegate` wraps another call (e.g. an identifier that
delegates to its qualified-data-name call); ``unwrap`` peels delegates.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, List, Optional

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


class FileControlEntryCall(_NamedCall):
    """A call to a file-control entry (a SELECT file name)."""

    call_type = CallTypeEnum.FILE_CONTROL_ENTRY_CALL

    def __init__(self, name, file_control_entry, program_unit, ctx) -> None:
        super().__init__(name, program_unit, ctx)
        self.file_control_entry = file_control_entry


class SpecialRegisterCall(Call):
    """A reference to a special register: ADDRESS OF, LENGTH OF, RETURN-CODE, ..."""

    call_type = CallTypeEnum.SPECIAL_REGISTER_CALL

    class SpecialRegisterType(Enum):
        ADDRESS_OF = "ADDRESS_OF"
        DATE = "DATE"
        DAY = "DAY"
        DAY_OF_WEEK = "DAY_OF_WEEK"
        DEBUG_CONTENTS = "DEBUG_CONTENTS"
        DEBUG_ITEM = "DEBUG_ITEM"
        DEBUG_LINE = "DEBUG_LINE"
        DEBUG_NAME = "DEBUG_NAME"
        DEBUG_SUB_1 = "DEBUG_SUB_1"
        DEBUG_SUB_2 = "DEBUG_SUB_2"
        DEBUG_SUB_3 = "DEBUG_SUB_3"
        LENGTH_OF = "LENGTH_OF"
        LINAGE_COUNTER = "LINAGE_COUNTER"
        LINE_COUNTER = "LINE_COUNTER"
        PAGE_COUNTER = "PAGE_COUNTER"
        RETURN_CODE = "RETURN_CODE"
        SHIFT_IN = "SHIFT_IN"
        SHIFT_OUT = "SHIFT_OUT"
        SORT_CONTROL = "SORT_CONTROL"
        SORT_CORE_SIZE = "SORT_CORE_SIZE"
        SORT_FILE_SIZE = "SORT_FILE_SIZE"
        SORT_MESSAGE = "SORT_MESSAGE"
        SORT_MODE_SIZE = "SORT_MODE_SIZE"
        SORT_RETURN = "SORT_RETURN"
        TALLY = "TALLY"
        TIME = "TIME"
        WHEN_COMPILED = "WHEN_COMPILED"

    def __init__(self, special_register_type, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = None
        self.special_register_type: Optional["SpecialRegisterCall.SpecialRegisterType"] = special_register_type
        self.identifier_call: Optional[Call] = None

    def set_identifier_call(self, call: Optional[Call]) -> None:
        self.identifier_call = call


class Subscript(CobolDivisionElement):
    """One subscript of a :class:`TableCall` (carries a value statement)."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.value_stmt = None


class TableCall(DataDescriptionEntryCall):
    """A subscripted data reference: ``name(subscript, ...)``.

    Mirrors ``TableCallImpl`` (extends ``DataDescriptionEntryCallImpl``): carries
    a list of :class:`Subscript` nodes built from the ``ctx.subscript()`` list.
    """

    call_type = CallTypeEnum.TABLE_CALL

    def __init__(self, name, data_description_entry, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(name, data_description_entry, program_unit, ctx)
        self.subscripts: List[Subscript] = []

    def add_subscript(self, subscript: Subscript) -> None:
        self.subscripts.append(subscript)


class FunctionCall(_NamedCall):
    """A call to an intrinsic/user function: ``FUNCTION name(...)``."""

    call_type = CallTypeEnum.FUNCTION_CALL


class MnemonicCall(_NamedCall):
    """A reference to a mnemonic-name (from SPECIAL-NAMES)."""

    call_type = CallTypeEnum.MNEMONIC_CALL


class EnvironmentCall(_NamedCall):
    """A reference to an environment-name (e.g. SYSIN, SYSOUT)."""

    call_type = CallTypeEnum.ENVIRONMENT_CALL


class IndexCall(_NamedCall):
    """A reference to an index name (declared via OCCURS INDEXED BY)."""

    call_type = CallTypeEnum.INDEX_CALL

    def __init__(self, index, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(getattr(index, "name", None), program_unit, ctx)
        self.index = index


class ReportCall(_NamedCall):
    """A call to a report description (RD in the REPORT SECTION)."""

    call_type = CallTypeEnum.REPORT_DESCRIPTION_CALL

    def __init__(self, name, report_description, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(name, program_unit, ctx)
        self.report_description = report_description


class CommunicationDescriptionEntryCall(_NamedCall):
    """A call to a communication description entry (CD in the COMMUNICATION SECTION)."""

    call_type = CallTypeEnum.COMMUNICATION_DESCRIPTION_ENTRY_CALL

    def __init__(self, name, communication_description_entry, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(name, program_unit, ctx)
        self.communication_description_entry = communication_description_entry
