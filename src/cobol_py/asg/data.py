"""Data division metamodel (Phase D).

Ports ``metamodel/data`` — the data-description hierarchy. Sections
(WorkingStorage / Linkage / LocalStorage / Communication / File) are
:class:`DataDescriptionEntryContainer` instances; each holds
:class:`DataDescriptionEntry` nodes built from Format1 (group/scalar), Format2
(rename, 66) and Format3 (condition, 88). The 01/02/... parent hierarchy is
resolved inline by level number (mirrors ``groupDataDescriptionEntry``).

Clause coverage is intentionally minimal for this phase: level number, name,
filler flag, and the picture string are captured; the full clause zoo
(OCCURS, REDEFINES, VALUE, USAGE, ...) is deferred. The goal of Phase D is
reference resolution — so a ``MOVE ... TO WS-A`` resolves ``WS-A`` to its
:class:`DataDescriptionEntry` via a :class:`DataDescriptionEntryCall`.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

from antlr4.ParserRuleContext import ParserRuleContext

from .base import CobolDivisionElement, Declaration

if TYPE_CHECKING:
    from .program import ProgramUnit


def _symbol(name: Optional[str]) -> Optional[str]:
    if name is None or name == "":
        return name
    return name.upper()


class DataDescriptionEntry(CobolDivisionElement, Declaration):
    """One data description entry (a COBOL data item declaration)."""

    LEVEL_NUMBER_CONDITION = 88
    LEVEL_NUMBER_RENAME = 66
    LEVEL_NUMBER_SCALAR = 77

    class Type(Enum):
        CONDITION = "CONDITION"
        EXEC_SQL = "EXEC_SQL"
        GROUP = "GROUP"
        RENAME = "RENAME"
        SCALAR = "SCALAR"

    def __init__(
        self,
        name: Optional[str],
        container: "Optional[DataDescriptionEntryContainer]",
        program_unit: "ProgramUnit",
        ctx: ParserRuleContext,
    ) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name
        self.data_description_entry_container = container
        self.level_number: Optional[int] = None
        self.parent_data_description_entry_group: Optional["DataDescriptionEntryGroup"] = None
        self.calls: List = []  # DataDescriptionEntryCall
        self.data_description_entry_predecessor = None
        self.data_description_entry_successor = None

    @property
    def data_description_entry_type(self) -> "DataDescriptionEntry.Type":
        return DataDescriptionEntry.Type.SCALAR

    def add_call(self, call) -> None:
        self.calls.append(call)


class DataDescriptionEntryGroup(DataDescriptionEntry):
    """A Format1 entry (level 01-49 or 77): may have child entries + a picture."""

    def __init__(self, name, container, program_unit, ctx) -> None:
        super().__init__(name, container, program_unit, ctx)
        self.data_description_entries: List[DataDescriptionEntry] = []
        self.picture: Optional[str] = None
        self.filler: bool = False
        self.filler_number: Optional[int] = None

    @property
    def data_description_entry_type(self) -> "DataDescriptionEntry.Type":
        return DataDescriptionEntry.Type.GROUP

    def add_data_description_entry(self, entry: DataDescriptionEntry) -> None:
        self.data_description_entries.append(entry)


class DataDescriptionEntryCondition(DataDescriptionEntry):
    """A Format3 entry (level 88, condition name)."""

    @property
    def data_description_entry_type(self) -> "DataDescriptionEntry.Type":
        return DataDescriptionEntry.Type.CONDITION


class DataDescriptionEntryRename(DataDescriptionEntry):
    """A Format2 entry (level 66, renames)."""

    @property
    def data_description_entry_type(self) -> "DataDescriptionEntry.Type":
        return DataDescriptionEntry.Type.RENAME


class DataDescriptionEntryContainer(CobolDivisionElement):
    """Base for sections (and file description entries) that hold data items."""

    class ContainerType(Enum):
        COMMUNICATION_SECTION = "COMMUNICATION_SECTION"
        FILE_DESCRIPTION_ENTRY = "FILE_DESCRIPTION_ENTRY"
        LINKAGE_SECTION = "LINKAGE_SECTION"
        LOCAL_STORAGE_SECTION = "LOCAL_STORAGE_SECTION"
        WORKING_STORAGE_SECTION = "WORKING_STORAGE_SECTION"

    container_type: Optional[ContainerType] = None

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self._entries: List[DataDescriptionEntry] = []
        self._by_name: Dict[Optional[str], List[DataDescriptionEntry]] = {}

    # -- building ------------------------------------------------------------

    def create_data_description_entry(self, current_group, ctx) -> Optional[DataDescriptionEntry]:
        """Dispatch on the entry format, build it, then group it under ``current_group``."""
        result: Optional[DataDescriptionEntry] = None
        if ctx.dataDescriptionEntryFormat1() is not None:
            result = self._add_group(ctx.dataDescriptionEntryFormat1())
        elif ctx.dataDescriptionEntryFormat2() is not None:
            result = self._add_rename(ctx.dataDescriptionEntryFormat2())
        elif ctx.dataDescriptionEntryFormat3() is not None:
            result = self._add_condition(ctx.dataDescriptionEntryFormat3())
        # DataDescriptionEntryExecSql deferred.

        if current_group is not None and result is not None:
            self._group(current_group, result)
        return result

    def _register_entry(self, name, entry: DataDescriptionEntry) -> None:
        self._entries.append(entry)
        self._by_name.setdefault(_symbol(name), []).append(entry)
        self._register(entry)

    def _add_group(self, ctx) -> DataDescriptionEntryGroup:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = DataDescriptionEntryGroup(name, self, self.program_unit, ctx)
            # level number
            if ctx.LEVEL_NUMBER_77() is not None:
                result.level_number = DataDescriptionEntry.LEVEL_NUMBER_SCALAR
            elif ctx.INTEGERLITERAL() is not None:
                result.level_number = _parse_int(ctx.INTEGERLITERAL().getText())
            # filler
            if ctx.FILLER() is not None:
                result.filler = True
                result.filler_number = self.compilation_unit.increment_filler_counter()
            # picture (raw string; full clause deferred)
            pic_clauses = ctx.dataPictureClause()
            if pic_clauses:
                result.picture = pic_clauses[0].getText()
            self._register_entry(name, result)
        return result

    def _add_condition(self, ctx) -> DataDescriptionEntryCondition:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = DataDescriptionEntryCondition(name, self, self.program_unit, ctx)
            result.level_number = DataDescriptionEntry.LEVEL_NUMBER_CONDITION
            self._register_entry(name, result)
        return result

    def _add_rename(self, ctx) -> DataDescriptionEntryRename:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = DataDescriptionEntryRename(name, self, self.program_unit, ctx)
            result.level_number = DataDescriptionEntry.LEVEL_NUMBER_RENAME
            self._register_entry(name, result)
        return result

    def _group(self, current_group: DataDescriptionEntryGroup, entry: DataDescriptionEntry) -> None:
        """Attach ``entry`` under the right ancestor by level number.

        Mirrors ``DataDescriptionEntryContainerImpl.groupDataDescriptionEntry``.
        """
        level = entry.level_number
        if not self._is_groupable(level):
            return
        current_level = current_group.level_number
        if current_level is not None and level > current_level:
            current_group.add_data_description_entry(entry)
            entry.parent_data_description_entry_group = current_group
        else:
            parent = current_group.parent_data_description_entry_group
            if parent is not None:
                self._group(parent, entry)

    @staticmethod
    def _is_groupable(level: Optional[int]) -> bool:
        return (
            level is not None
            and level != DataDescriptionEntry.LEVEL_NUMBER_SCALAR
            and level != DataDescriptionEntry.LEVEL_NUMBER_RENAME
        )

    # -- access --------------------------------------------------------------

    @property
    def data_description_entries(self) -> List[DataDescriptionEntry]:
        return self._entries

    @property
    def root_data_description_entries(self) -> List[DataDescriptionEntry]:
        return [e for e in self._entries if e.parent_data_description_entry_group is None]

    def get_data_description_entries(self, name: Optional[str] = None) -> List[DataDescriptionEntry]:
        if name is None:
            return list(self._entries)
        return list(self._by_name.get(_symbol(name), []))

    def get_data_description_entry(self, name: str) -> Optional[DataDescriptionEntry]:
        entries = self._by_name.get(_symbol(name), [])
        return entries[0] if entries else None


class WorkingStorageSection(DataDescriptionEntryContainer):
    container_type = DataDescriptionEntryContainer.ContainerType.WORKING_STORAGE_SECTION


class LinkageSection(DataDescriptionEntryContainer):
    container_type = DataDescriptionEntryContainer.ContainerType.LINKAGE_SECTION


class LocalStorageSection(DataDescriptionEntryContainer):
    container_type = DataDescriptionEntryContainer.ContainerType.LOCAL_STORAGE_SECTION


class CommunicationSection(DataDescriptionEntryContainer):
    container_type = DataDescriptionEntryContainer.ContainerType.COMMUNICATION_SECTION


class FileDescriptionEntry(DataDescriptionEntryContainer, Declaration):
    """An FD entry. Also a data-description container for its 01-level records."""

    container_type = DataDescriptionEntryContainer.ContainerType.FILE_DESCRIPTION_ENTRY

    def __init__(self, name, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name


class FileSection(CobolDivisionElement):
    """The FILE SECTION: holds file description entries (FDs)."""

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self._file_description_entries: List[FileDescriptionEntry] = []

    def add_file_description_entry(self, ctx) -> Optional[FileDescriptionEntry]:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = FileDescriptionEntry(name, self.program_unit, ctx)
            self._file_description_entries.append(result)
            self._register(result)
            # data records under the FD
            for entry_ctx in ctx.dataDescriptionEntry():
                current_group = None
                entry = result.create_data_description_entry(current_group, entry_ctx)
                if isinstance(entry, DataDescriptionEntryGroup):
                    current_group = entry
        return result

    @property
    def file_description_entries(self) -> List[FileDescriptionEntry]:
        return self._file_description_entries


class DataDivision(CobolDivisionElement):
    """The DATA DIVISION: holds the data sections."""

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.working_storage_section: Optional[WorkingStorageSection] = None
        self.linkage_section: Optional[LinkageSection] = None
        self.local_storage_section: Optional[LocalStorageSection] = None
        self.communication_section: Optional[CommunicationSection] = None
        self.file_section: Optional[FileSection] = None
        # Report / Screen / ProgramLibrary / DataBase sections deferred.

    def _add_container_section(self, cls, attr, ctx):
        result = self._get_element(ctx)
        if result is None:
            result = cls(self.program_unit, ctx)
            current_group = None
            for entry_ctx in ctx.dataDescriptionEntry():
                entry = result.create_data_description_entry(current_group, entry_ctx)
                if isinstance(entry, DataDescriptionEntryGroup):
                    current_group = entry
            setattr(self, attr, result)
            self._register(result)
        return result

    def add_working_storage_section(self, ctx) -> WorkingStorageSection:
        self.working_storage_section = self._add_container_section(
            WorkingStorageSection, "working_storage_section", ctx
        )
        return self.working_storage_section

    def add_linkage_section(self, ctx) -> LinkageSection:
        self.linkage_section = self._add_container_section(LinkageSection, "linkage_section", ctx)
        return self.linkage_section

    def add_local_storage_section(self, ctx) -> LocalStorageSection:
        self.local_storage_section = self._add_container_section(
            LocalStorageSection, "local_storage_section", ctx
        )
        return self.local_storage_section

    def add_communication_section(self, ctx) -> CommunicationSection:
        self.communication_section = self._add_container_section(
            CommunicationSection, "communication_section", ctx
        )
        return self.communication_section

    def add_file_section(self, ctx) -> FileSection:
        result = self._get_element(ctx)
        if result is None:
            result = FileSection(self.program_unit, ctx)
            for fd_ctx in ctx.fileDescriptionEntry():
                result.add_file_description_entry(fd_ctx)
            self.file_section = result
            self._register(result)
        return result


def _parse_int(text: Optional[str]) -> Optional[int]:
    if text is None:
        return None
    try:
        return int(text.strip())
    except (ValueError, AttributeError):
        return None
