"""Communication section metamodel (Phase D3).

Ports ``metamodel/data/communication`` — the COMMUNICATION SECTION with
INPUT / OUTPUT / INPUT-OUTPUT CD entries and their clause models.

The CD entries mirror Java's three-format dispatch:
Format1 → CommunicationDescriptionEntryInput (9 clause types)
Format2 → CommunicationDescriptionEntryOutput (6 clause types)
Format3 → CommunicationDescriptionEntryInputOutput (6 clause types)
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

from antlr4.ParserRuleContext import ParserRuleContext

from .base import CobolDivisionElement, Declaration
from .data import DataDescriptionEntryContainer

if TYPE_CHECKING:
    from .program import ProgramUnit


def _symbol(name: Optional[str]) -> Optional[str]:
    if name is None or name == "":
        return name
    return name.upper()


def _has(ctx, token_name: str) -> bool:
    accessor = getattr(ctx, token_name, None)
    return callable(accessor) and accessor() is not None


# ============================================================================
# CommunicationDescriptionEntry base
# ============================================================================

class CommunicationDescriptionEntryType(Enum):
    INPUT = "INPUT"
    INPUT_OUTPUT = "INPUT_OUTPUT"
    OUTPUT = "OUTPUT"


class CommunicationDescriptionEntry(CobolDivisionElement, Declaration):
    """Base for CD entries (INPUT / OUTPUT / INPUT-OUTPUT)."""

    def __init__(
        self,
        name: Optional[str],
        program_unit: "ProgramUnit",
        ctx: ParserRuleContext,
    ) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name
        self.calls: List = []

    def add_call(self, call) -> None:
        self.calls.append(call)

    @property
    def communication_description_entry_type(self) -> CommunicationDescriptionEntryType:
        raise NotImplementedError


# ============================================================================
# Clause models (14 types — all simple Call-wrappers except where noted)
# ============================================================================

class MessageCountClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_desc_call = None


class MessageDateClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_desc_call = None


class MessageTimeClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_desc_call = None


class SymbolicSourceClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_desc_call = None


class SymbolicQueueClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_desc_call = None


class SymbolicSubQueueClauseType(Enum):
    SUB_QUEUE_1 = "SUB_QUEUE_1"
    SUB_QUEUE_2 = "SUB_QUEUE_2"
    SUB_QUEUE_3 = "SUB_QUEUE_3"


class SymbolicSubQueueClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_desc_call = None
        self.symbolic_sub_queue_clause_type: Optional[SymbolicSubQueueClauseType] = None


class SymbolicDestinationClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_desc_call = None


class SymbolicTerminalClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_desc_call = None


class TextLengthClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_desc_call = None


class EndKeyClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_desc_call = None


class ErrorKeyClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_desc_call = None


class StatusKeyClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_desc_call = None


class DestinationCountClause(CobolDivisionElement):
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_desc_call = None


class DestinationTableClause(CobolDivisionElement):
    """``OCCURS integerLiteral [INDEXED BY indexName+]`` clause for OUTPUT CD."""

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.occurs_integer_literal = None  # IntegerLiteral
        self.index_calls: List = []


# ============================================================================
# Concrete entry types
# ============================================================================

class CommunicationDescriptionEntryInput(CommunicationDescriptionEntry):
    """Format1 CD entry: ``CD cdName FOR INITIAL INPUT ...``."""

    def __init__(self, name, program_unit, ctx):
        super().__init__(name, program_unit, ctx)
        # 9 clause attributes
        self.end_key_clause: Optional[EndKeyClause] = None
        self.message_count_clause: Optional[MessageCountClause] = None
        self.message_date_clause: Optional[MessageDateClause] = None
        self.message_time_clause: Optional[MessageTimeClause] = None
        self.status_key_clause: Optional[StatusKeyClause] = None
        self.symbolic_queue_clause: Optional[SymbolicQueueClause] = None
        self.symbolic_source_clause: Optional[SymbolicSourceClause] = None
        self.symbolic_sub_queue_clause: Optional[SymbolicSubQueueClause] = None
        self.text_length_clause: Optional[TextLengthClause] = None

    @property
    def communication_description_entry_type(self):
        return CommunicationDescriptionEntryType.INPUT

    # -- clause builders (registry-check-first, matching Java) -----------------

    def _build_clause(self, cls, attr, ctx, **fields):
        result = self._get_element(ctx)
        if result is None:
            result = cls(self.program_unit, ctx)
            for k, v in fields.items():
                setattr(result, k, v)
            self._register(result)
        setattr(self, attr, result)
        return result

    def add_end_key_clause(self, ctx):
        return self._build_clause(
            EndKeyClause, "end_key_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_message_count_clause(self, ctx):
        return self._build_clause(
            MessageCountClause, "message_count_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_message_date_clause(self, ctx):
        return self._build_clause(
            MessageDateClause, "message_date_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_message_time_clause(self, ctx):
        return self._build_clause(
            MessageTimeClause, "message_time_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_status_key_clause(self, ctx):
        return self._build_clause(
            StatusKeyClause, "status_key_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_symbolic_queue_clause(self, ctx):
        return self._build_clause(
            SymbolicQueueClause, "symbolic_queue_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_symbolic_source_clause(self, ctx):
        return self._build_clause(
            SymbolicSourceClause, "symbolic_source_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_symbolic_sub_queue_clause(self, ctx):
        sub = self._get_element(ctx)
        if sub is None:
            sub = SymbolicSubQueueClause(self.program_unit, ctx)
            sub.data_desc_call = self.create_call(ctx.dataDescName())
            # type
            if _has(ctx, "SUB_QUEUE_1"):
                sub.symbolic_sub_queue_clause_type = SymbolicSubQueueClauseType.SUB_QUEUE_1
            elif _has(ctx, "SUB_QUEUE_2"):
                sub.symbolic_sub_queue_clause_type = SymbolicSubQueueClauseType.SUB_QUEUE_2
            elif _has(ctx, "SUB_QUEUE_3"):
                sub.symbolic_sub_queue_clause_type = SymbolicSubQueueClauseType.SUB_QUEUE_3
            self._register(sub)
        self.symbolic_sub_queue_clause = sub
        return sub

    def add_text_length_clause(self, ctx):
        return self._build_clause(
            TextLengthClause, "text_length_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )


class CommunicationDescriptionEntryOutput(CommunicationDescriptionEntry):
    """Format2 CD entry: ``CD cdName FOR OUTPUT ...``."""

    def __init__(self, name, program_unit, ctx):
        super().__init__(name, program_unit, ctx)
        self.destination_count_clause: Optional[DestinationCountClause] = None
        self.destination_table_clause: Optional[DestinationTableClause] = None
        self.error_key_clause: Optional[ErrorKeyClause] = None
        self.status_key_clause: Optional[StatusKeyClause] = None
        self.symbolic_destination_clause: Optional[SymbolicDestinationClause] = None
        self.text_length_clause: Optional[TextLengthClause] = None

    @property
    def communication_description_entry_type(self):
        return CommunicationDescriptionEntryType.OUTPUT

    def _build_clause(self, cls, attr, ctx, **fields):
        result = self._get_element(ctx)
        if result is None:
            result = cls(self.program_unit, ctx)
            for k, v in fields.items():
                setattr(result, k, v)
            self._register(result)
        setattr(self, attr, result)
        return result

    def add_destination_count_clause(self, ctx):
        return self._build_clause(
            DestinationCountClause, "destination_count_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_destination_table_clause(self, ctx):
        result = self._get_element(ctx)
        if result is None:
            result = DestinationTableClause(self.program_unit, ctx)
            if ctx.integerLiteral() is not None:
                result.occurs_integer_literal = self.create_integer_literal(
                    ctx.integerLiteral()
                )
            for idx_ctx in ctx.indexName():
                result.index_calls.append(self.create_call(idx_ctx))
            self._register(result)
        self.destination_table_clause = result
        return result

    def add_error_key_clause(self, ctx):
        return self._build_clause(
            ErrorKeyClause, "error_key_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_status_key_clause(self, ctx):
        return self._build_clause(
            StatusKeyClause, "status_key_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_symbolic_destination_clause(self, ctx):
        return self._build_clause(
            SymbolicDestinationClause, "symbolic_destination_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_text_length_clause(self, ctx):
        return self._build_clause(
            TextLengthClause, "text_length_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )


class CommunicationDescriptionEntryInputOutput(CommunicationDescriptionEntry):
    """Format3 CD entry: ``CD cdName FOR INITIAL I-O ...``."""

    def __init__(self, name, program_unit, ctx):
        super().__init__(name, program_unit, ctx)
        self.end_key_clause: Optional[EndKeyClause] = None
        self.message_date_clause: Optional[MessageDateClause] = None
        self.message_time_clause: Optional[MessageTimeClause] = None
        self.status_key_clause: Optional[StatusKeyClause] = None
        self.symbolic_terminal_clause: Optional[SymbolicTerminalClause] = None
        self.text_length_clause: Optional[TextLengthClause] = None

    @property
    def communication_description_entry_type(self):
        return CommunicationDescriptionEntryType.INPUT_OUTPUT

    def _build_clause(self, cls, attr, ctx, **fields):
        result = self._get_element(ctx)
        if result is None:
            result = cls(self.program_unit, ctx)
            for k, v in fields.items():
                setattr(result, k, v)
            self._register(result)
        setattr(self, attr, result)
        return result

    def add_end_key_clause(self, ctx):
        return self._build_clause(
            EndKeyClause, "end_key_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_message_date_clause(self, ctx):
        return self._build_clause(
            MessageDateClause, "message_date_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_message_time_clause(self, ctx):
        return self._build_clause(
            MessageTimeClause, "message_time_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_status_key_clause(self, ctx):
        return self._build_clause(
            StatusKeyClause, "status_key_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_symbolic_terminal_clause(self, ctx):
        return self._build_clause(
            SymbolicTerminalClause, "symbolic_terminal_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )

    def add_text_length_clause(self, ctx):
        return self._build_clause(
            TextLengthClause, "text_length_clause", ctx,
            data_desc_call=self.create_call(ctx.dataDescName()),
        )


# ============================================================================
# CommunicationSection — the container
# ============================================================================

class _CDSymbolTableEntry:
    def __init__(self):
        self._entries: List[CommunicationDescriptionEntry] = []

    def add_entry(self, entry: CommunicationDescriptionEntry):
        self._entries.append(entry)

    def get_entry(self) -> Optional[CommunicationDescriptionEntry]:
        return self._entries[0] if self._entries else None

    def get_entries(self) -> List[CommunicationDescriptionEntry]:
        return self._entries


class CommunicationSection(DataDescriptionEntryContainer):
    """The COMMUNICATION SECTION: holds CD entries and their data items."""

    container_type = DataDescriptionEntryContainer.ContainerType.COMMUNICATION_SECTION

    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)
        self._cd_entries: List[CommunicationDescriptionEntry] = []
        self._cd_by_name: Dict[Optional[str], _CDSymbolTableEntry] = {}

    # -- dispatch ------------------------------------------------------------

    def create_communication_description_entry(
        self, ctx
    ) -> Optional[CommunicationDescriptionEntry]:
        if ctx.communicationDescriptionEntryFormat1() is not None:
            return self._add_input(ctx.communicationDescriptionEntryFormat1())
        elif ctx.communicationDescriptionEntryFormat2() is not None:
            return self._add_output(ctx.communicationDescriptionEntryFormat2())
        elif ctx.communicationDescriptionEntryFormat3() is not None:
            return self._add_input_output(ctx.communicationDescriptionEntryFormat3())
        return None

    # -- builders (matching Java add* methods) --------------------------------

    def _add_input(self, ctx) -> CommunicationDescriptionEntryInput:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = CommunicationDescriptionEntryInput(name, self.program_unit, ctx)
            self._populate_input_clauses(result, ctx)
            self._register_cd_entry(name, result)
        return result

    def _add_output(self, ctx) -> CommunicationDescriptionEntryOutput:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = CommunicationDescriptionEntryOutput(name, self.program_unit, ctx)
            self._populate_output_clauses(result, ctx)
            self._register_cd_entry(name, result)
        return result

    def _add_input_output(self, ctx) -> CommunicationDescriptionEntryInputOutput:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = CommunicationDescriptionEntryInputOutput(name, self.program_unit, ctx)
            self._populate_io_clauses(result, ctx)
            self._register_cd_entry(name, result)
        return result

    # -- clause population (inline, matching Java's inline-time dispatch) -----

    def _populate_input_clauses(self, entry: CommunicationDescriptionEntryInput, ctx):
        for c in ctx.messageDateClause():
            entry.add_message_date_clause(c)
        for c in ctx.messageTimeClause():
            entry.add_message_time_clause(c)
        for c in ctx.symbolicTerminalClause():
            pass  # Terminal belongs to IO, not Input; grammar may include it in Format1 ctx
        for c in ctx.textLengthClause():
            entry.add_text_length_clause(c)
        for c in ctx.endKeyClause():
            entry.add_end_key_clause(c)
        for c in ctx.statusKeyClause():
            entry.add_status_key_clause(c)
        for c in ctx.messageCountClause():
            entry.add_message_count_clause(c)
        for c in ctx.symbolicSourceClause():
            entry.add_symbolic_source_clause(c)
        for c in ctx.symbolicQueueClause():
            entry.add_symbolic_queue_clause(c)
        for c in ctx.symbolicSubQueueClause():
            entry.add_symbolic_sub_queue_clause(c)

    def _populate_output_clauses(self, entry: CommunicationDescriptionEntryOutput, ctx):
        for c in ctx.destinationCountClause():
            entry.add_destination_count_clause(c)
        for c in ctx.destinationTableClause():
            entry.add_destination_table_clause(c)
        for c in ctx.textLengthClause():
            entry.add_text_length_clause(c)
        for c in ctx.errorKeyClause():
            entry.add_error_key_clause(c)
        for c in ctx.symbolicDestinationClause():
            entry.add_symbolic_destination_clause(c)
        for c in ctx.statusKeyClause():
            entry.add_status_key_clause(c)

    def _populate_io_clauses(self, entry: CommunicationDescriptionEntryInputOutput, ctx):
        for c in ctx.messageDateClause():
            entry.add_message_date_clause(c)
        for c in ctx.messageTimeClause():
            entry.add_message_time_clause(c)
        for c in ctx.textLengthClause():
            entry.add_text_length_clause(c)
        for c in ctx.endKeyClause():
            entry.add_end_key_clause(c)
        for c in ctx.statusKeyClause():
            entry.add_status_key_clause(c)
        for c in ctx.symbolicTerminalClause():
            entry.add_symbolic_terminal_clause(c)

    # -- symbol table ---------------------------------------------------------

    def _register_cd_entry(self, name, entry):
        self._cd_entries.append(entry)
        self._cd_by_name.setdefault(_symbol(name), _CDSymbolTableEntry()).add_entry(entry)
        self._register(entry)

    @property
    def communication_description_entries(self) -> List[CommunicationDescriptionEntry]:
        return self._cd_entries

    def get_communication_description_entry(
        self, name: str
    ) -> Optional[CommunicationDescriptionEntry]:
        e = self._cd_by_name.get(_symbol(name))
        return e.get_entry() if e else None

    def get_communication_description_entries(
        self, name: str
    ) -> List[CommunicationDescriptionEntry]:
        e = self._cd_by_name.get(_symbol(name))
        return e.get_entries() if e else []
