"""Data division metamodel (Phase D).

Ports ``metamodel/data`` — the data-description hierarchy. Sections
(WorkingStorage / Linkage / LocalStorage / Communication / File) are
:class:`DataDescriptionEntryContainer` instances; each holds
:class:`DataDescriptionEntry` nodes built from Format1 (group/scalar), Format2
(rename, 66) and Format3 (condition, 88). The 01/02/... parent hierarchy is
resolved inline by level number (mirrors ``groupDataDescriptionEntry``).

Phase D2 extends clause coverage to all 27 COBOL data description clauses
defined in ``dataDescriptionEntryFormat1`` (plus ValueClause for Format2/3).
Each clause is a typed :class:`CobolDivisionElement` registered in the ASG
element registry, matching the proleap Java metamodel clause-for-clause.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

from antlr4.ParserRuleContext import ParserRuleContext

from .base import CobolDivisionElement, Declaration
from .factory import ProcedureUnitFactory

if TYPE_CHECKING:
    from .program import ProgramUnit


def _symbol(name: Optional[str]) -> Optional[str]:
    if name is None or name == "":
        return name
    return name.upper()


# -- helper: typed-token dispatch (avoids substring false-positives) ----------

def _has(ctx, token_name: str) -> bool:
    """Return ``True`` if the named ANTLR typed token is present on ``ctx``."""
    accessor = getattr(ctx, token_name, None)
    return callable(accessor) and accessor() is not None


def _untagged_exec_sql(ctx) -> str:
    """Extract body text from EXECSQLLINE tokens, stripping ``*>EXECSQL`` / ``}`` tags.

    Mirrors ``TagUtils.getUntaggedText`` in the Java source.
    """
    from ..preprocessor.constants import EXEC_SQL_TAG

    tokens_getter = getattr(ctx, "EXECSQLLINE", None)
    if tokens_getter is None or not callable(tokens_getter):
        return ctx.getText()
    token_nodes = tokens_getter()
    if not token_nodes:
        return ""
    parts = []
    for tn in (token_nodes if isinstance(token_nodes, list) else [token_nodes]):
        text = tn.getText() if hasattr(tn, "getText") else str(tn)
        for t in (EXEC_SQL_TAG, "}"):
            text = text.replace(t, "")
        parts.append(text.strip())
    return " ".join(parts).strip()


# -- clause enums ------------------------------------------------------------

class UsageClauseType(Enum):
    """Ports ``UsageClause.UsageClauseType`` (26 canonical COBOL usage values)."""
    ADDRESS = "ADDRESS"
    BINARY = "BINARY"
    BINARY_EXTENDED = "BINARY_EXTENDED"
    BINARY_TRUNCATED = "BINARY_TRUNCATED"
    BIT = "BIT"
    COMP = "COMP"
    COMP_1 = "COMP_1"
    COMP_2 = "COMP_2"
    COMP_3 = "COMP_3"
    COMP_4 = "COMP_4"
    COMP_5 = "COMP_5"
    CONTROL_POINT = "CONTROL_POINT"
    DATE = "DATE"
    DISPLAY = "DISPLAY"
    DISPLAY_1 = "DISPLAY_1"
    DOUBLE = "DOUBLE"
    EVENT = "EVENT"
    FUNCTION_POINTER = "FUNCTION_POINTER"
    INDEX = "INDEX"
    KANJI = "KANJI"
    LOCK = "LOCK"
    NATIONAL = "NATIONAL"
    PACKED_DECIMAL = "PACKED_DECIMAL"
    POINTER = "POINTER"
    PROCEDURE_POINTER = "PROCEDURE_POINTER"
    REAL = "REAL"
    SQL = "SQL"
    TASK = "TASK"


class SignClauseType(Enum):
    LEADING = "LEADING"
    TRAILING = "TRAILING"


class SynchronizedType(Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class JustifiedType(Enum):
    JUSTIFIED = "JUSTIFIED"
    JUSTIFIED_RIGHT = "JUSTIFIED_RIGHT"


class CommonOwnLocalType(Enum):
    COMMON = "COMMON"
    LOCAL = "LOCAL"
    OWN = "OWN"


class TypeClauseTimeType(Enum):
    SHORT_DATE = "SHORT_DATE"
    LONG_DATE = "LONG_DATE"
    NUMERIC_DATE = "NUMERIC_DATE"
    NUMERIC_TIME = "NUMERIC_TIME"
    LONG_TIME = "LONG_TIME"
    CLOB = "CLOB"
    BLOB = "BLOB"
    DBCLOB = "DBCLOB"


class UsingClauseType(Enum):
    CONVENTION = "CONVENTION"
    LANGUAGE = "LANGUAGE"


class ReceivedByType(Enum):
    CONTENT = "CONTENT"
    REFERENCE = "REFERENCE"


class IntegerStringPrimitiveType(Enum):
    INTEGER = "INTEGER"
    STRING = "STRING"


class OccursSortOrder(Enum):
    ASCENDING = "ASCENDING"
    DESCENDING = "DESCENDING"


class BlockContainsUnit(Enum):
    CHARACTERS = "CHARACTERS"
    RECORDS = "RECORDS"


class LabelRecordsClauseType(Enum):
    DATA_NAMES = "DATA_NAMES"
    OMITTED = "OMITTED"
    STANDARD = "STANDARD"


# ============================================================================
# data description entries (Format1 group/scalar, Format2 rename, Format3 cond)
# ============================================================================

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
    """A Format1 entry (level 01-49 or 77): may have child entries and clauses.

    Each COBOL clause (PICTURE, VALUE, OCCURS, REDEFINES, ...) is stored as a
    typed :class:`CobolDivisionElement` attribute, built lazily via ``add_*``
    factory methods that follow the registry-check-first pattern.
    """

    def __init__(self, name, container, program_unit, ctx) -> None:
        super().__init__(name, container, program_unit, ctx)
        self.data_description_entries: List[DataDescriptionEntry] = []
        self.filler: bool = False
        self.filler_number: Optional[int] = None

        # --- clause storage (one per clause type; multi-occurrence are List) ---
        self.picture_clause: Optional[PictureClause] = None
        self.value_clause: Optional[ValueClause] = None
        self.occurs_clauses: List[OccursClause] = []
        self.usage_clause: Optional[UsageClause] = None
        self.redefines_clause: Optional[RedefinesClause] = None
        self.sign_clause: Optional[SignClause] = None
        self.synchronized_clause: Optional[SynchronizedClause] = None
        self.justified_clause: Optional[JustifiedClause] = None
        self.blank_when_zero_clause: Optional[BlankWhenZeroClause] = None
        self.external_clause: Optional[ExternalClause] = None
        self.global_clause: Optional[GlobalClause] = None
        self.thread_local_clause: Optional[ThreadLocalClause] = None
        self.common_own_local_clause: Optional[CommonOwnLocalClause] = None
        self.aligned_clause: Optional[AlignedClause] = None
        self.record_area_clause: Optional[RecordAreaClause] = None
        self.type_clause: Optional[TypeClause] = None
        self.type_def_clause: Optional[TypeDefClause] = None
        self.using_clause: Optional[UsingClause] = None
        self.received_by_clause: Optional[ReceivedByClause] = None
        self.with_lower_bounds_clause: Optional[WithLowerBoundsClause] = None
        self.integer_string_clause: Optional[IntegerStringClause] = None

    @property
    def data_description_entry_type(self) -> "DataDescriptionEntry.Type":
        return DataDescriptionEntry.Type.GROUP

    def add_data_description_entry(self, entry: DataDescriptionEntry) -> None:
        self.data_description_entries.append(entry)

    # -- clause builders (registry-check-first pattern) -----------------------

    def _build_clause(self, clause_cls, attr, ctx, **fields):
        """Generic: get-or-create a clause, set fields, register, store."""
        result = self._get_element(ctx)
        if result is None:
            result = clause_cls(self.program_unit, ctx)
            for k, v in fields.items():
                setattr(result, k, v)
            setattr(self, attr, result)
            self._register(result)
        return result

    def add_picture_clause(self, ctx) -> "PictureClause":
        result = self._get_element(ctx)
        if result is None:
            result = PictureClause(self.program_unit, ctx)
            pic = ctx.pictureString()
            if pic is not None:
                result.picture_string = pic.getText()
            self.picture_clause = result
            self._register(result)
        return result

    def add_value_clause(self, ctx) -> "ValueClause":
        result = self._get_element(ctx)
        if result is None:
            result = ValueClause(self.program_unit, ctx)
            for interval_ctx in ctx.dataValueInterval():
                interval = result.add_value_interval(interval_ctx)
                result.value_intervals.append(interval)
            self.value_clause = result
            self._register(result)
        return result

    def add_occurs_clause(self, ctx) -> "OccursClause":
        result = self._get_element(ctx)
        if result is None:
            result = OccursClause(self.program_unit, ctx)
            # from (identifier | integerLiteral)
            ident = ctx.identifier()
            lit = ctx.integerLiteral()
            if ident is not None or lit is not None:
                result._from = self.create_value_stmt(ident, lit)
            # to (dataOccursTo -> integerLiteral)
            to_ctx = ctx.dataOccursTo()
            if to_ctx is not None:
                il = to_ctx.integerLiteral()
                if il is not None:
                    result._to = self.create_integer_literal(il)
            # depending
            depending_ctx = ctx.dataOccursDepending()
            if depending_ctx is not None:
                result.add_occurs_depending(depending_ctx)
            # sort clauses
            for sort_ctx in ctx.dataOccursSort():
                result.add_occurs_sort(sort_ctx)
            # indexed (may appear multiple times under the * repeat)
            for indexed_ctx in ctx.dataOccursIndexed():
                result.add_occurs_indexed(indexed_ctx)
            self.occurs_clauses.append(result)
            self._register(result)
        return result

    def add_usage_clause(self, ctx) -> "UsageClause":
        result = self._get_element(ctx)
        if result is None:
            result = UsageClause(self.program_unit, ctx)
            result.usage_clause_type = _dispatch_usage(ctx)
            self.usage_clause = result
            self._register(result)
        return result

    def add_redefines_clause(self, ctx) -> "RedefinesClause":
        result = self._get_element(ctx)
        if result is None:
            result = RedefinesClause(self.program_unit, ctx)
            dname = ctx.dataName()
            if dname is not None:
                result.redefines_call = self.create_call(dname)
            self.redefines_clause = result
            self._register(result)
        return result

    def add_sign_clause(self, ctx) -> "SignClause":
        result = self._get_element(ctx)
        if result is None:
            result = SignClause(self.program_unit, ctx)
            if _has(ctx, "LEADING"):
                result.sign_clause_type = SignClauseType.LEADING
            elif _has(ctx, "TRAILING"):
                result.sign_clause_type = SignClauseType.TRAILING
            result.separate = _has(ctx, "SEPARATE")
            self.sign_clause = result
            self._register(result)
        return result

    def add_synchronized_clause(self, ctx) -> "SynchronizedClause":
        result = self._get_element(ctx)
        if result is None:
            result = SynchronizedClause(self.program_unit, ctx)
            if _has(ctx, "LEFT"):
                result.sync = SynchronizedType.LEFT
            elif _has(ctx, "RIGHT"):
                result.sync = SynchronizedType.RIGHT
            self.synchronized_clause = result
            self._register(result)
        return result

    def add_justified_clause(self, ctx) -> "JustifiedClause":
        result = self._get_element(ctx)
        if result is None:
            result = JustifiedClause(self.program_unit, ctx)
            if _has(ctx, "RIGHT"):
                result.justified = JustifiedType.JUSTIFIED_RIGHT
            else:
                result.justified = JustifiedType.JUSTIFIED
            self.justified_clause = result
            self._register(result)
        return result

    def add_blank_when_zero_clause(self, ctx) -> "BlankWhenZeroClause":
        result = self._get_element(ctx)
        if result is None:
            result = BlankWhenZeroClause(self.program_unit, ctx)
            result.blank_when_zero = True
            self.blank_when_zero_clause = result
            self._register(result)
        return result

    def add_external_clause(self, ctx) -> "ExternalClause":
        result = self._get_element(ctx)
        if result is None:
            result = ExternalClause(self.program_unit, ctx)
            result.external = True
            lit = ctx.literal()
            if lit is not None:
                result.by_literal_value_stmt = self.create_literal_value_stmt(lit)
            self.external_clause = result
            self._register(result)
        return result

    def add_global_clause(self, ctx) -> "GlobalClause":
        result = self._get_element(ctx)
        if result is None:
            result = GlobalClause(self.program_unit, ctx)
            result.global_ = True
            self.global_clause = result
            self._register(result)
        return result

    def add_thread_local_clause(self, ctx) -> "ThreadLocalClause":
        result = self._get_element(ctx)
        if result is None:
            result = ThreadLocalClause(self.program_unit, ctx)
            result.thread_local = True
            self.thread_local_clause = result
            self._register(result)
        return result

    def add_common_own_local_clause(self, ctx) -> "CommonOwnLocalClause":
        result = self._get_element(ctx)
        if result is None:
            result = CommonOwnLocalClause(self.program_unit, ctx)
            if _has(ctx, "COMMON"):
                result.invariance = CommonOwnLocalType.COMMON
            elif _has(ctx, "OWN"):
                result.invariance = CommonOwnLocalType.OWN
            elif _has(ctx, "LOCAL"):
                result.invariance = CommonOwnLocalType.LOCAL
            self.common_own_local_clause = result
            self._register(result)
        return result

    def add_aligned_clause(self, ctx) -> "AlignedClause":
        return self._build_clause(AlignedClause, "aligned_clause", ctx, aligned=True)

    def add_record_area_clause(self, ctx) -> "RecordAreaClause":
        return self._build_clause(RecordAreaClause, "record_area_clause", ctx, record_area=True)

    def add_type_clause(self, ctx) -> "TypeClause":
        result = self._get_element(ctx)
        if result is None:
            result = TypeClause(self.program_unit, ctx)
            result.time_type = _dispatch_type_clause(ctx)
            # CLOB/BLOB/DBCLOB carry a length literal
            lit = ctx.integerLiteral()
            if lit is not None:
                result.length = int(lit.getText())
            self.type_clause = result
            self._register(result)
        return result

    def add_type_def_clause(self, ctx) -> "TypeDefClause":
        return self._build_clause(TypeDefClause, "type_def_clause", ctx, type_def=True)

    def add_using_clause(self, ctx) -> "UsingClause":
        result = self._get_element(ctx)
        if result is None:
            result = UsingClause(self.program_unit, ctx)
            if _has(ctx, "LANGUAGE"):
                result.using_clause_type = UsingClauseType.LANGUAGE
            elif _has(ctx, "CONVENTION"):
                result.using_clause_type = UsingClauseType.CONVENTION
            # OF value: cobolWord | dataName
            cw = getattr(ctx, "cobolWord", None)
            dn = getattr(ctx, "dataName", None)
            if cw is not None:
                cw_result = cw() if callable(cw) else None
            else:
                cw_result = None
            dn_result = dn() if (dn is not None and callable(dn)) else None
            of_ctx = cw_result
            if of_ctx is None and dn_result is not None:
                # create_value_stmt handles both identifier and literal
                pass
            if of_ctx is not None:
                result.of_value_stmt = self.create_value_stmt(of_ctx)
            self.using_clause = result
            self._register(result)
        return result

    def add_received_by_clause(self, ctx) -> "ReceivedByClause":
        result = self._get_element(ctx)
        if result is None:
            result = ReceivedByClause(self.program_unit, ctx)
            if _has(ctx, "CONTENT"):
                result.received_by = ReceivedByType.CONTENT
            elif _has(ctx, "REFERENCE") or _has(ctx, "REF"):
                result.received_by = ReceivedByType.REFERENCE
            self.received_by_clause = result
            self._register(result)
        return result

    def add_with_lower_bounds_clause(self, ctx) -> "WithLowerBoundsClause":
        return self._build_clause(WithLowerBoundsClause, "with_lower_bounds_clause", ctx, with_lower_bounds=True)

    def add_integer_string_clause(self, ctx) -> "IntegerStringClause":
        result = self._get_element(ctx)
        if result is None:
            result = IntegerStringClause(self.program_unit, ctx)
            if _has(ctx, "INTEGER"):
                result.primitive_type = IntegerStringPrimitiveType.INTEGER
            elif _has(ctx, "STRING"):
                result.primitive_type = IntegerStringPrimitiveType.STRING
            self.integer_string_clause = result
            self._register(result)
        return result


class DataDescriptionEntryCondition(DataDescriptionEntry):
    """A Format3 entry (level 88, condition name)."""

    def __init__(self, name, container, program_unit, ctx) -> None:
        super().__init__(name, container, program_unit, ctx)
        self.value_clause: Optional[ValueClause] = None

    @property
    def data_description_entry_type(self) -> "DataDescriptionEntry.Type":
        return DataDescriptionEntry.Type.CONDITION

    def add_value_clause(self, ctx) -> "ValueClause":
        result = self._get_element(ctx)
        if result is None:
            result = ValueClause(self.program_unit, ctx)
            for interval_ctx in ctx.dataValueInterval():
                interval = result.add_value_interval(interval_ctx)
                result.value_intervals.append(interval)
            self.value_clause = result
            self._register(result)
        return result


class DataDescriptionEntryRename(DataDescriptionEntry):
    """A Format2 entry (level 66, renames)."""

    def __init__(self, name, container, program_unit, ctx) -> None:
        super().__init__(name, container, program_unit, ctx)
        self.renames_clause: Optional[RenamesClause] = None

    @property
    def data_description_entry_type(self) -> "DataDescriptionEntry.Type":
        return DataDescriptionEntry.Type.RENAME

    def add_renames_clause(self, ctx) -> "RenamesClause":
        result = self._get_element(ctx)
        if result is None:
            result = RenamesClause(self.program_unit, ctx)
            qdns = ctx.qualifiedDataName()
            if qdns:
                result._from = self.create_call(qdns[0])
                result.calls.append(result._from)
                if len(qdns) > 1:
                    result._to = self.create_call(qdns[1])
                    result.calls.append(result._to)
            self.renames_clause = result
            self._register(result)
        return result


class DataDescriptionEntryExecSql(DataDescriptionEntry):
    """An ``EXEC SQL INCLUDE ... END-EXEC.`` entry in the data division.

    Ports ``DataDescriptionEntryExecSql``. Has no level number or name;
    the body text is extracted via EXECSQLLINE token stripping.
    """

    def __init__(self, container, program_unit, ctx) -> None:
        super().__init__(None, container, program_unit, ctx)
        self.exec_sql_text: Optional[str] = None

    @property
    def data_description_entry_type(self) -> "DataDescriptionEntry.Type":
        return DataDescriptionEntry.Type.EXEC_SQL


# ============================================================================
# clause model classes (each mirrors a Java *Clause interface + Impl)
# ============================================================================

class PictureClause(CobolDivisionElement):
    """PICTURE / PIC IS? <picture-string>. Ports ``PictureClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.picture_string: Optional[str] = None


class ValueInterval(CobolDivisionElement):
    """One VALUE interval (``from [THROUGH|THRU to]``). Ports ``ValueIntervalImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.from_value_stmt = None
        self.to_value_stmt: Optional = None

    @property
    def through(self) -> bool:
        """True when this interval has a THROUGH / THRU upper bound."""
        return self.to_value_stmt is not None


class ValueClause(CobolDivisionElement):
    """VALUE / VALUES (IS | ARE)? <interval> ... Ports ``ValueClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.value_intervals: List[ValueInterval] = []

    def add_value_interval(self, ctx) -> ValueInterval:
        result = self._get_element(ctx)
        if result is None:
            result = ValueInterval(self.program_unit, ctx)
            # from
            from_ctx = ctx.dataValueIntervalFrom()
            if from_ctx is not None:
                result.from_value_stmt = self.create_value_stmt(
                    from_ctx.literal(), from_ctx.cobolWord()
                )
            # to
            to_ctx = ctx.dataValueIntervalTo()
            if to_ctx is not None:
                result.to_value_stmt = self.create_value_stmt(to_ctx.literal())
            self._register(result)
        return result

    # ValueClause needs create_value_stmt — delegate to the entry scope.
    # During build, the caller (DataDescriptionEntryGroup.add_value_clause) is a
    # CobolDivisionElement which has create_value_stmt via ProgramUnitElement.
    # We route through __init__'s program_unit reference.

    def create_value_stmt(self, *ctxs):
        """Delegate value-stmt creation via the inherited factory method."""
        return ProcedureUnitFactory.create_value_stmt(self, *[c for c in ctxs if c is not None])

    def create_call(self, ctx):
        """Delegate call creation via the inherited factory method."""
        return ProcedureUnitFactory.create_call(self, ctx)


class OccursDepending(CobolDivisionElement):
    """DEPENDING ON <qualifiedDataName>. Ports ``OccursDependingImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.depending_on_call = None


class OccursSort(CobolDivisionElement):
    """ASCENDING / DESCENDING KEY? IS? <keys>. Ports ``OccursSortImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.order: Optional[OccursSortOrder] = None
        self.key_calls: List = []


class Index(CobolDivisionElement):
    """An index name (from INDEXED BY). Ports ``Index`` interface + impl."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name: Optional[str] = None
        self._calls: List = []  # IndexCall

    def add_call(self, call) -> None:
        self._calls.append(call)

    @property
    def calls(self) -> List:
        return self._calls


class OccursIndexed(CobolDivisionElement):
    """INDEXED BY <indices>. Ports ``OccursIndexedImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.indices: List[Index] = []

    def add_index(self, ctx) -> Index:
        result = self._get_element(ctx)
        if result is None:
            result = Index(self.program_unit, ctx)
            result.name = ctx.getText()
            self.indices.append(result)
            self._register(result)
        return result

    def get_index(self, name: str) -> Optional[Index]:
        for idx in self.indices:
            if idx.name and idx.name.upper() == name.upper():
                return idx
        return None


class OccursClause(CobolDivisionElement):
    """OCCURS <from> [TO <to>] [DEPENDING ON ...] [SORT ...] [INDEXED ...].
    Ports ``OccursClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self._from = None  # ValueStmt
        self._to = None  # IntegerLiteral
        self.occurs_depending: Optional[OccursDepending] = None
        self.occurs_indexed: Optional[OccursIndexed] = None
        self.occurs_sorts: List[OccursSort] = []

    def add_occurs_depending(self, ctx) -> OccursDepending:
        result = self._get_element(ctx)
        if result is None:
            result = OccursDepending(self.program_unit, ctx)
            qdn = ctx.qualifiedDataName()
            if qdn is not None:
                result.depending_on_call = ProcedureUnitFactory.create_call(self, qdn)
            self.occurs_depending = result
            self._register(result)
        return result

    def add_occurs_sort(self, ctx) -> OccursSort:
        result = self._get_element(ctx)
        if result is None:
            result = OccursSort(self.program_unit, ctx)
            if _has(ctx, "ASCENDING"):
                result.order = OccursSortOrder.ASCENDING
            elif _has(ctx, "DESCENDING"):
                result.order = OccursSortOrder.DESCENDING
            for qdn in ctx.qualifiedDataName():
                result.key_calls.append(ProcedureUnitFactory.create_call(self, qdn))
            self.occurs_sorts.append(result)
            self._register(result)
        return result

    def add_occurs_indexed(self, ctx) -> OccursIndexed:
        result = self._get_element(ctx)
        if result is None:
            result = OccursIndexed(self.program_unit, ctx)
            for index_ctx in ctx.indexName():
                result.add_index(index_ctx)
            self.occurs_indexed = result
            self._register(result)
        return result


class UsageClause(CobolDivisionElement):
    """USAGE IS? <type>. Ports ``UsageClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.usage_clause_type: Optional[UsageClauseType] = None


class RedefinesClause(CobolDivisionElement):
    """REDEFINES <dataName>. Ports ``RedefinesClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.redefines_call = None


class RenamesClause(CobolDivisionElement):
    """RENAMES <qdn> [THROUGH|THRU <qdn>]. Ports ``RenamesClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self._from = None
        self._to = None
        self.calls: List = []


class SignClause(CobolDivisionElement):
    """SIGN IS? LEADING|TRAILING [SEPARATE]. Ports ``SignClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.sign_clause_type: Optional[SignClauseType] = None
        self.separate: bool = False


class SynchronizedClause(CobolDivisionElement):
    """SYNCHRONIZED / SYNC [LEFT | RIGHT]. Ports ``SynchronizedClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.sync: Optional[SynchronizedType] = None


class JustifiedClause(CobolDivisionElement):
    """JUSTIFIED / JUST [RIGHT]. Ports ``JustifiedClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.justified: Optional[JustifiedType] = None


class BlankWhenZeroClause(CobolDivisionElement):
    """BLANK WHEN ZERO / ZEROS / ZEROES. Ports ``BlankWhenZeroClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.blank_when_zero: bool = False


class ExternalClause(CobolDivisionElement):
    """IS? EXTERNAL [BY <literal>]. Ports ``ExternalClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.external: bool = False
        self.by_literal_value_stmt = None


class GlobalClause(CobolDivisionElement):
    """IS? GLOBAL. Ports ``GlobalClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.global_: bool = False


class ThreadLocalClause(CobolDivisionElement):
    """IS? THREAD-LOCAL. Ports ``ThreadLocalClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.thread_local: bool = False


class CommonOwnLocalClause(CobolDivisionElement):
    """COMMON | OWN | LOCAL. Ports ``CommonOwnLocalClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.invariance: Optional[CommonOwnLocalType] = None


class AlignedClause(CobolDivisionElement):
    """ALIGNED. Ports ``AlignedClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.aligned: bool = False


class RecordAreaClause(CobolDivisionElement):
    """RECORD AREA. Ports ``RecordAreaClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.record_area: bool = False


class TypeClause(CobolDivisionElement):
    """TYPE IS? <type> [<length>]. Ports ``TypeClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.time_type: Optional[TypeClauseTimeType] = None
        self.length: Optional[int] = None


class TypeDefClause(CobolDivisionElement):
    """IS? TYPEDEF. Ports ``TypeDefClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.type_def: bool = False


class UsingClause(CobolDivisionElement):
    """USING (LANGUAGE | CONVENTION) OF? <value>. Ports ``UsingClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.using_clause_type: Optional[UsingClauseType] = None
        self.of_value_stmt = None


class ReceivedByClause(CobolDivisionElement):
    """RECEIVED? BY? (CONTENT | REFERENCE | REF). Ports ``ReceivedByClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.received_by: Optional[ReceivedByType] = None


class WithLowerBoundsClause(CobolDivisionElement):
    """WITH? LOWER BOUNDS. Ports ``WithLowerBoundsClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.with_lower_bounds: bool = False


class IntegerStringClause(CobolDivisionElement):
    """INTEGER | STRING. Ports ``IntegerStringClauseImpl``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.primitive_type: Optional[IntegerStringPrimitiveType] = None


# -- FD (File Description Entry) clause models (10 clauses) -----------------

class BlockContainsClause(CobolDivisionElement):
    """BLOCK CONTAINS <from> [TO <to>] RECORDS|CHARACTERS. Ports ``BlockContainsClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.unit: Optional[BlockContainsUnit] = None
        self.from_: Optional = None  # IntegerLiteral
        self.to: Optional = None  # IntegerLiteral


class CodeSetClause(CobolDivisionElement):
    """CODE-SET IS <alphabet>. Ports ``CodeSetClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.alphabet_name: Optional[str] = None


class DataRecordsClause(CobolDivisionElement):
    """DATA RECORD IS <names>. Ports ``DataRecordsClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_calls: List = []


class FDExternalClause(CobolDivisionElement):
    """IS? EXTERNAL (at FD level). Ports ``data.file.ExternalClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.external: bool = False


class FDGlobalClause(CobolDivisionElement):
    """IS? GLOBAL (at FD level). Ports ``data.file.GlobalClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.global_: bool = False


class LabelRecordsClause(CobolDivisionElement):
    """LABEL RECORD IS|ARE STANDARD|OMITTED|<names>. Ports ``LabelRecordsClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.label_records_clause_type: Optional[LabelRecordsClauseType] = None
        self.data_calls: List = []


class LinageClause(CobolDivisionElement):
    """LINAGE IS <lines> [FOOTING <ft>] [TOP <top>] [BOTTOM <btm>]. Ports ``LinageClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.number_of_lines_value_stmt = None
        self.footing_at_value_stmt = None
        self.lines_at_top_value_stmt = None
        self.lines_at_bottom_value_stmt = None


class RecordContainsClause(CobolDivisionElement):
    """RECORD CONTAINS <from> [TO <to>] [VARYING ...]. Ports ``RecordContainsClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.varying: bool = False
        self.from_: Optional = None  # IntegerLiteral
        self.to: Optional = None  # IntegerLiteral
        self.depending_on_call = None


class ReportClause(CobolDivisionElement):
    """REPORT IS|ARE <reports>. Ports ``data.file.ReportClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.report_calls: List = []


class ValueOfNameValuePair:
    """One (name, value) pair inside VALUE OF. Ports ``ValueOfNameValuePair``."""

    __slots__ = ("name_call", "value")

    def __init__(self) -> None:
        self.name_call = None
        self.value = None  # ValueStmt


class ValueOfClause(CobolDivisionElement):
    """VALUE OF <name-value-pair>+. Ports ``ValueOfClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.value_pairs: List[ValueOfNameValuePair] = []


# -- utility for usage-clause typed-token dispatch ---------------------------
# The usage clause has 25 alternatives; we map them in the grammar's precedence
# order (the order they appear in the grammar).

_USAGE_TOKEN_MAP = [
    ("ADDRESS", UsageClauseType.ADDRESS),
    ("BINARY_TRUNCATED", UsageClauseType.BINARY_TRUNCATED),
    ("BINARY_EXTENDED", UsageClauseType.BINARY_EXTENDED),
    ("BINARY", UsageClauseType.BINARY),
    ("BIT", UsageClauseType.BIT),
    ("COMP_5", UsageClauseType.COMP_5),
    ("COMP_4", UsageClauseType.COMP_4),
    ("COMP_3", UsageClauseType.COMP_3),
    ("COMP_2", UsageClauseType.COMP_2),
    ("COMP_1", UsageClauseType.COMP_1),
    ("COMP", UsageClauseType.COMP),
    ("COMPUTATIONAL_5", UsageClauseType.COMP_5),
    ("COMPUTATIONAL_4", UsageClauseType.COMP_4),
    ("COMPUTATIONAL_3", UsageClauseType.COMP_3),
    ("COMPUTATIONAL_2", UsageClauseType.COMP_2),
    ("COMPUTATIONAL_1", UsageClauseType.COMP_1),
    ("COMPUTATIONAL", UsageClauseType.COMP),
    ("CONTROL_POINT", UsageClauseType.CONTROL_POINT),
    ("DATE", UsageClauseType.DATE),
    ("DISPLAY_1", UsageClauseType.DISPLAY_1),
    ("DISPLAY", UsageClauseType.DISPLAY),
    ("DOUBLE", UsageClauseType.DOUBLE),
    ("EVENT", UsageClauseType.EVENT),
    ("FUNCTION_POINTER", UsageClauseType.FUNCTION_POINTER),
    ("INDEX", UsageClauseType.INDEX),
    ("KANJI", UsageClauseType.KANJI),
    ("LOCK", UsageClauseType.LOCK),
    ("NATIONAL", UsageClauseType.NATIONAL),
    ("PACKED_DECIMAL", UsageClauseType.PACKED_DECIMAL),
    ("POINTER", UsageClauseType.POINTER),
    ("PROCEDURE_POINTER", UsageClauseType.PROCEDURE_POINTER),
    ("REAL", UsageClauseType.REAL),
    ("SQL", UsageClauseType.SQL),
    ("TASK", UsageClauseType.TASK),
]


def _dispatch_usage(ctx) -> Optional[UsageClauseType]:
    for token, usg_type in _USAGE_TOKEN_MAP:
        if _has(ctx, token):
            return usg_type
    return None


# -- utility for type-clause dispatch ----------------------------------------

_TYPE_TOKEN_MAP = [
    ("SHORT_DATE", TypeClauseTimeType.SHORT_DATE),
    ("LONG_DATE", TypeClauseTimeType.LONG_DATE),
    ("NUMERIC_DATE", TypeClauseTimeType.NUMERIC_DATE),
    ("NUMERIC_TIME", TypeClauseTimeType.NUMERIC_TIME),
    ("LONG_TIME", TypeClauseTimeType.LONG_TIME),
    ("CLOB", TypeClauseTimeType.CLOB),
    ("BLOB", TypeClauseTimeType.BLOB),
    ("DBCLOB", TypeClauseTimeType.DBCLOB),
]


def _dispatch_type_clause(ctx) -> Optional[TypeClauseTimeType]:
    for token, tt in _TYPE_TOKEN_MAP:
        if _has(ctx, token):
            return tt
    return None


# ============================================================================
# data description entry container (builds entries for a section)
# ============================================================================

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
        elif ctx.dataDescriptionEntryExecSql() is not None:
            result = self._add_exec_sql(ctx.dataDescriptionEntryExecSql())

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

            # -- clauses (matching Java's inline clause dispatch order) -------

            # picture
            for c in ctx.dataPictureClause():
                result.add_picture_clause(c)
            # redefines
            for c in ctx.dataRedefinesClause():
                result.add_redefines_clause(c)
            # integer-string
            for c in ctx.dataIntegerStringClause():
                result.add_integer_string_clause(c)
            # external
            for c in ctx.dataExternalClause():
                result.add_external_clause(c)
            # global
            for c in ctx.dataGlobalClause():
                result.add_global_clause(c)
            # type-def
            for c in ctx.dataTypeDefClause():
                result.add_type_def_clause(c)
            # thread-local
            for c in ctx.dataThreadLocalClause():
                result.add_thread_local_clause(c)
            # common-own-local
            for c in ctx.dataCommonOwnLocalClause():
                result.add_common_own_local_clause(c)
            # type
            for c in ctx.dataTypeClause():
                result.add_type_clause(c)
            # using
            for c in ctx.dataUsingClause():
                result.add_using_clause(c)
            # usage
            for c in ctx.dataUsageClause():
                result.add_usage_clause(c)
            # value
            for c in ctx.dataValueClause():
                result.add_value_clause(c)
            # received-by
            for c in ctx.dataReceivedByClause():
                result.add_received_by_clause(c)
            # occurs (may appear multiple times, each is a separate clause)
            for c in ctx.dataOccursClause():
                result.add_occurs_clause(c)
            # sign
            for c in ctx.dataSignClause():
                result.add_sign_clause(c)
            # synchronized
            for c in ctx.dataSynchronizedClause():
                result.add_synchronized_clause(c)
            # justified
            for c in ctx.dataJustifiedClause():
                result.add_justified_clause(c)
            # blank-when-zero
            for c in ctx.dataBlankWhenZeroClause():
                result.add_blank_when_zero_clause(c)
            # with-lower-bounds
            for c in ctx.dataWithLowerBoundsClause():
                result.add_with_lower_bounds_clause(c)
            # aligned
            for c in ctx.dataAlignedClause():
                result.add_aligned_clause(c)
            # record-area
            for c in ctx.dataRecordAreaClause():
                result.add_record_area_clause(c)

            self._register_entry(name, result)
        return result

    def _add_condition(self, ctx) -> DataDescriptionEntryCondition:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = DataDescriptionEntryCondition(name, self, self.program_unit, ctx)
            result.level_number = DataDescriptionEntry.LEVEL_NUMBER_CONDITION
            # condition entries always carry a value clause
            vc = ctx.dataValueClause()
            if vc is not None:
                result.add_value_clause(vc)
            self._register_entry(name, result)
        return result

    def _add_rename(self, ctx) -> DataDescriptionEntryRename:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = DataDescriptionEntryRename(name, self, self.program_unit, ctx)
            result.level_number = DataDescriptionEntry.LEVEL_NUMBER_RENAME
            rc = ctx.dataRenamesClause()
            if rc is not None:
                result.add_renames_clause(rc)
            self._register_entry(name, result)
        return result

    def _add_exec_sql(self, ctx) -> "DataDescriptionEntryExecSql":
        result = self._get_element(ctx)
        if result is None:
            result = DataDescriptionEntryExecSql(self, self.program_unit, ctx)
            # Extract body text, stripping exec-sql tags (matching Java TagUtils)
            result.exec_sql_text = _untagged_exec_sql(ctx)
            self._register_entry(None, result)
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


# ============================================================================
# sections & file description entries
# ============================================================================

class WorkingStorageSection(DataDescriptionEntryContainer):
    container_type = DataDescriptionEntryContainer.ContainerType.WORKING_STORAGE_SECTION


class LinkageSection(DataDescriptionEntryContainer):
    container_type = DataDescriptionEntryContainer.ContainerType.LINKAGE_SECTION


class LocalStorageSection(DataDescriptionEntryContainer):
    container_type = DataDescriptionEntryContainer.ContainerType.LOCAL_STORAGE_SECTION


# CommunicationSection is now fully modeled in communication.py.
# Removed stub — see _CommunicationSection placeholder.


class FileDescriptionEntry(DataDescriptionEntryContainer, Declaration):
    """An FD entry. Also a data-description container for its 01-level records.

    Ports ``data.file.FileDescriptionEntry``. In addition to the inherited
    data-description entry container behavior, it holds the FD-level clauses
    (BlockContains, LabelRecords, Linage, ...).
    """

    container_type = DataDescriptionEntryContainer.ContainerType.FILE_DESCRIPTION_ENTRY

    def __init__(self, name, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name
        # FD clause storage
        self.block_contains_clause: Optional[BlockContainsClause] = None
        self.code_set_clause: Optional[CodeSetClause] = None
        self.data_records_clause: Optional[DataRecordsClause] = None
        self.fd_external_clause: Optional[FDExternalClause] = None
        self.fd_global_clause: Optional[FDGlobalClause] = None
        self.label_records_clause: Optional[LabelRecordsClause] = None
        self.linage_clause: Optional[LinageClause] = None
        self.record_contains_clause: Optional[RecordContainsClause] = None
        self.report_clause: Optional[ReportClause] = None
        self.value_of_clause: Optional[ValueOfClause] = None

    def add_block_contains_clause(self, ctx) -> BlockContainsClause:
        result = self._get_element(ctx)
        if result is None:
            result = BlockContainsClause(self.program_unit, ctx)
            if _has(ctx, "CHARACTERS"):
                result.unit = BlockContainsUnit.CHARACTERS
            elif _has(ctx, "RECORDS") or _has(ctx, "RECORD"):
                result.unit = BlockContainsUnit.RECORDS
            il = ctx.integerLiteral()
            if il is not None:
                result.from_ = self.create_integer_literal(il)
            to_ctx = ctx.blockContainsTo()
            if to_ctx is not None and to_ctx.integerLiteral() is not None:
                result.to = self.create_integer_literal(to_ctx.integerLiteral())
            self.block_contains_clause = result
            self._register(result)
        return result

    def add_code_set_clause(self, ctx) -> CodeSetClause:
        result = self._get_element(ctx)
        if result is None:
            result = CodeSetClause(self.program_unit, ctx)
            an = ctx.alphabetName()
            if an is not None:
                result.alphabet_name = an.getText()
            self.code_set_clause = result
            self._register(result)
        return result

    def add_data_records_clause(self, ctx) -> DataRecordsClause:
        result = self._get_element(ctx)
        if result is None:
            result = DataRecordsClause(self.program_unit, ctx)
            for dn in ctx.dataName():
                result.data_calls.append(self.create_call(dn))
            self.data_records_clause = result
            self._register(result)
        return result

    def add_fd_external_clause(self, ctx) -> FDExternalClause:
        result = self._get_element(ctx)
        if result is None:
            result = FDExternalClause(self.program_unit, ctx)
            result.external = True
            self.fd_external_clause = result
            self._register(result)
        return result

    def add_fd_global_clause(self, ctx) -> FDGlobalClause:
        result = self._get_element(ctx)
        if result is None:
            result = FDGlobalClause(self.program_unit, ctx)
            result.global_ = True
            self.fd_global_clause = result
            self._register(result)
        return result

    def add_label_records_clause(self, ctx) -> LabelRecordsClause:
        result = self._get_element(ctx)
        if result is None:
            result = LabelRecordsClause(self.program_unit, ctx)
            if _has(ctx, "STANDARD"):
                result.label_records_clause_type = LabelRecordsClauseType.STANDARD
            elif _has(ctx, "OMITTED"):
                result.label_records_clause_type = LabelRecordsClauseType.OMITTED
            else:
                result.label_records_clause_type = LabelRecordsClauseType.DATA_NAMES
            for dn in ctx.dataName():
                result.data_calls.append(self.create_call(dn))
            self.label_records_clause = result
            self._register(result)
        return result

    def add_linage_clause(self, ctx) -> LinageClause:
        result = self._get_element(ctx)
        if result is None:
            result = LinageClause(self.program_unit, ctx)
            nlines = ctx.linageNumberOfLines()
            if nlines is not None:
                result.number_of_lines_value_stmt = self.create_value_stmt(
                    nlines.identifier(), nlines.integerLiteral()
                )
            ft = ctx.linageFootingAt()
            if ft is not None:
                result.footing_at_value_stmt = self.create_value_stmt(
                    ft.identifier(), ft.integerLiteral()
                )
            top = ctx.linageLinesAtTop()
            if top is not None:
                result.lines_at_top_value_stmt = self.create_value_stmt(
                    top.identifier(), top.integerLiteral()
                )
            btm = ctx.linageLinesAtBottom()
            if btm is not None:
                result.lines_at_bottom_value_stmt = self.create_value_stmt(
                    btm.identifier(), btm.integerLiteral()
                )
            self.linage_clause = result
            self._register(result)
        return result

    def add_record_contains_clause(self, ctx) -> RecordContainsClause:
        result = self._get_element(ctx)
        if result is None:
            result = RecordContainsClause(self.program_unit, ctx)
            fmt2 = ctx.recordContainsClauseFormat2()
            fmt1 = ctx.recordContainsClauseFormat1()
            sub = fmt2 or fmt1
            if fmt2 is not None:
                result.varying = True
            if sub is not None:
                il = sub.integerLiteral()
                if il is not None:
                    result.from_ = self.create_integer_literal(il)
                dc = getattr(sub, "recordContainsDependingOn", lambda: None)()
                if dc is not None and dc.qualifiedDataName() is not None:
                    result.depending_on_call = self.create_call(dc.qualifiedDataName())
            self.record_contains_clause = result
            self._register(result)
        return result

    def add_report_clause(self, ctx) -> ReportClause:
        result = self._get_element(ctx)
        if result is None:
            result = ReportClause(self.program_unit, ctx)
            for rn in ctx.reportName():
                result.report_calls.append(self.create_call(rn))
            self.report_clause = result
            self._register(result)
        return result

    def add_value_of_clause(self, ctx) -> ValueOfClause:
        result = self._get_element(ctx)
        if result is None:
            result = ValueOfClause(self.program_unit, ctx)
            for pair_ctx in ctx.valueOfNameValuePair():
                pair = ValueOfNameValuePair()
                dn = pair_ctx.dataName()
                if dn is not None:
                    pair.name_call = self.create_call(dn)
                lit = pair_ctx.literal()
                if lit is not None:
                    pair.value = self.create_value_stmt(lit)
                result.value_pairs.append(pair)
            self.value_of_clause = result
            self._register(result)
        return result


class FileSection(CobolDivisionElement):
    """The FILE SECTION: holds file description entries (FDs)."""

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self._file_description_entries: List[FileDescriptionEntry] = []

    def add_file_description_entry(self, ctx) -> Optional[FileDescriptionEntry]:
        result = self._get_element(ctx)
        if result is None:
            # FD name: the fileName context holds the FD's file name
            fn = ctx.fileName()
            name = fn.getText() if fn is not None else self.determine_name(ctx)
            result = FileDescriptionEntry(name, self.program_unit, ctx)
            self._file_description_entries.append(result)
            self._register(result)
            # FD clauses
            for clause_ctx in (ctx.fileDescriptionEntryClause() or []):
                if clause_ctx.blockContainsClause() is not None:
                    result.add_block_contains_clause(clause_ctx.blockContainsClause())
                elif clause_ctx.codeSetClause() is not None:
                    result.add_code_set_clause(clause_ctx.codeSetClause())
                elif clause_ctx.dataRecordsClause() is not None:
                    result.add_data_records_clause(clause_ctx.dataRecordsClause())
                elif clause_ctx.labelRecordsClause() is not None:
                    result.add_label_records_clause(clause_ctx.labelRecordsClause())
                elif clause_ctx.linageClause() is not None:
                    result.add_linage_clause(clause_ctx.linageClause())
                elif clause_ctx.recordContainsClause() is not None:
                    result.add_record_contains_clause(clause_ctx.recordContainsClause())
                elif clause_ctx.reportClause() is not None:
                    result.add_report_clause(clause_ctx.reportClause())
                elif clause_ctx.valueOfClause() is not None:
                    result.add_value_of_clause(clause_ctx.valueOfClause())
                elif clause_ctx.externalClause() is not None:
                    result.add_fd_external_clause(clause_ctx.externalClause())
                elif clause_ctx.globalClause() is not None:
                    result.add_fd_global_clause(clause_ctx.globalClause())
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


# ============================================================================
# data division
# ============================================================================

class DataDivision(CobolDivisionElement):
    """The DATA DIVISION: holds the data sections."""

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.working_storage_section: Optional[WorkingStorageSection] = None
        self.linkage_section: Optional[LinkageSection] = None
        self.local_storage_section: Optional[LocalStorageSection] = None
        self.communication_section = None  # Lazy-imported CommunicationSection
        self.file_section: Optional[FileSection] = None
        self.data_base_section = None  # Lazy-imported DataBaseSection (mainframe)
        self.program_library_section = None  # Lazy-imported (mainframe)
        self.report_section = None  # Lazy-imported (mainframe)
        self.screen_section = None  # Lazy-imported (mainframe)

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

    def add_communication_section(self, ctx):
        from .communication import CommunicationSection as CS

        result = self._get_element(ctx)
        if result is None:
            result = CS(self.program_unit, ctx)
            # Grammar: (communicationDescriptionEntry | dataDescriptionEntry)*
            # Both are top-level children of the communication section.
            current_group = None
            for child_idx in range(ctx.getChildCount()):
                child = ctx.getChild(child_idx)
                cls_name = type(child).__name__
                if cls_name == "CommunicationDescriptionEntryContext":
                    result.create_communication_description_entry(child)
                elif cls_name == "CommunicationDescriptionEntryFormat1Context":
                    result.create_communication_description_entry(child.parentCtx or child)
                elif cls_name.startswith("DataDescriptionEntry"):
                    entry = result.create_data_description_entry(current_group, child)
                    if isinstance(entry, DataDescriptionEntryGroup):
                        current_group = entry
            self.communication_section = result
            self._register(result)
        return result

    def add_file_section(self, ctx) -> FileSection:
        result = self._get_element(ctx)
        if result is None:
            result = FileSection(self.program_unit, ctx)
            for fd_ctx in ctx.fileDescriptionEntry():
                result.add_file_description_entry(fd_ctx)
            self.file_section = result
            self._register(result)
        return result

    def add_data_base_section(self, ctx):
        from .mainframe import DataBaseSection as DBS

        result = self._get_element(ctx)
        if result is None:
            result = DBS(self.program_unit, ctx)
            for entry_ctx in ctx.dataBaseSectionEntry():
                result.add_data_base_section_entry(entry_ctx)
            self.data_base_section = result
            self._register(result)
        return result

    def add_program_library_section(self, ctx):
        from .mainframe import ProgramLibrarySection as PLS

        result = self._get_element(ctx)
        if result is None:
            result = PLS(self.program_unit, ctx)
            for child_idx in range(ctx.getChildCount()):
                child = ctx.getChild(child_idx)
                cls_name = type(child).__name__
                if cls_name in ("LibraryDescriptionEntryContext",
                                 "LibraryDescriptionEntryFormat1Context",
                                 "LibraryDescriptionEntryFormat2Context"):
                    result.create_library_description_entry(
                        child.parentCtx if hasattr(child, "parentCtx") else child
                    )
            self.program_library_section = result
            self._register(result)
        return result

    def add_report_section(self, ctx):
        from .mainframe import ReportSection as RS

        result = self._get_element(ctx)
        if result is None:
            result = RS(self.program_unit, ctx)
            for child_idx in range(ctx.getChildCount()):
                child = ctx.getChild(child_idx)
                cls_name = type(child).__name__
                if "ReportDescriptionContext" in cls_name and "Entry" not in cls_name and "Group" not in cls_name:
                    result.add_report_description(child)
            self.report_section = result
            self._register(result)
        return result

    def add_screen_section(self, ctx):
        from .mainframe import ScreenSection as SS

        result = self._get_element(ctx)
        if result is None:
            result = SS(self.program_unit, ctx)
            for child_idx in range(ctx.getChildCount()):
                child = ctx.getChild(child_idx)
                if type(child).__name__ == "ScreenDescriptionEntryContext":
                    result.add_screen_description_entry(child)
            self.screen_section = result
            self._register(result)
        return result


def _parse_int(text: Optional[str]) -> Optional[int]:
    if text is None:
        return None
    try:
        return int(text.strip())
    except (ValueError, AttributeError):
        return None
