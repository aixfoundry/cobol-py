"""Environment division metamodel (Phase E).

Ports ``metamodel/environment`` including configuration, input-output (file-control
clauses), special-names, and I-O-control. File-control entries carry the full set
of 12 SELECT sub-clauses (AccessMode, Assign, Organization, RecordKey, ...) from
Java's ``filecontrol/`` package. Configuration and special-names remain stubs.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

from antlr4.ParserRuleContext import ParserRuleContext

from .base import CobolDivisionElement, NamedElement

if TYPE_CHECKING:
    from .data import FileDescriptionEntry
    from .program import ProgramUnit


def _symbol(name: Optional[str]) -> Optional[str]:
    if name is None or name == "":
        return name
    return name.upper()


def _has(ctx, token_name: str) -> bool:
    accessor = getattr(ctx, token_name, None)
    return callable(accessor) and accessor() is not None


# -- file-control clause enums -----------------------------------------------

class AccessMode(Enum):
    DYNAMIC = "DYNAMIC"
    EXCLUSIVE = "EXCLUSIVE"
    RANDOM = "RANDOM"
    SEQUENTIAL = "SEQUENTIAL"


class OrganizationMode(Enum):
    INDEXED = "INDEXED"
    RELATIVE = "RELATIVE"
    SEQUENTIAL = "SEQUENTIAL"


class OrganizationClauseType(Enum):
    BINARY = "BINARY"
    LINE = "LINE"
    RECORD = "RECORD"
    RECORD_BINARY = "RECORD_BINARY"


class AssignClauseType(Enum):
    CALL = "CALL"
    DISK = "DISK"
    DISPLAY = "DISPLAY"
    KEYBOARD = "KEYBOARD"
    PORT = "PORT"
    PRINTER = "PRINTER"
    READER = "READER"
    REMOTE = "REMOTE"
    TAPE = "TAPE"
    VIRTUAL = "VIRTUAL"


class RecordDelimiterClauseType(Enum):
    ASSIGNMENT = "ASSIGNMENT"
    IMPLICIT = "IMPLICIT"
    STANDARD_1 = "STANDARD_1"


# -- file-control clause models (12 clauses) ----------------------------------

class SelectClause(CobolDivisionElement, NamedElement):
    """SELECT [OPTIONAL] <file-name>. Ports ``SelectClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name: Optional[str] = None
        self.optional: bool = False
        self.file_call = None


class AssignClause(CobolDivisionElement):
    """ASSIGN TO <device> [<type>]. Ports ``AssignClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.assign_clause_type: Optional[AssignClauseType] = None
        self.to_value_stmt = None


class AccessModeClause(CobolDivisionElement):
    """ACCESS MODE IS <mode>. Ports ``AccessModeClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.mode: Optional[AccessMode] = None


class OrganizationClause(CobolDivisionElement):
    """ORGANIZATION IS <mode> [RECORD <type>]. Ports ``OrganizationClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.mode: Optional[OrganizationMode] = None
        self.organization_clause_type: Optional[OrganizationClauseType] = None


class FileStatusClause(CobolDivisionElement):
    """FILE STATUS IS <data-name> [<data-name-2>]. Ports ``FileStatusClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_call = None
        self.data_call2 = None


class PasswordClause(CobolDivisionElement):
    """PASSWORD IS <data-name>. Ports ``PasswordClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_call = None


class RecordKeyClause(CobolDivisionElement):
    """RECORD KEY IS <qdn> [PASSWORD <data>]. Ports ``RecordKeyClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.record_key_call = None
        self.password_clause: Optional[PasswordClause] = None


class AlternateRecordKeyClause(CobolDivisionElement):
    """ALTERNATE RECORD KEY IS <qdn> [PASSWORD <data>]. Ports ``AlternateRecordKeyClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.data_call = None
        self.password_clause: Optional[PasswordClause] = None


class RelativeKeyClause(CobolDivisionElement):
    """RELATIVE KEY IS <qdn>. Ports ``RelativeKeyClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.relative_key_call = None


class PaddingCharacterClause(CobolDivisionElement):
    """PADDING CHARACTER IS <value>. Ports ``PaddingCharacterClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.value_stmt = None


class RecordDelimiterClause(CobolDivisionElement):
    """RECORD DELIMITER IS <type>. Ports ``RecordDelimiterClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.record_delimiter_clause_type: Optional[RecordDelimiterClauseType] = None
        self.value_stmt = None


class ReserveClause(CobolDivisionElement):
    """RESERVE <integer> AREAS. Ports ``ReserveClause``."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.value_stmt = None  # IntegerLiteralValueStmt


# -- dispatch helpers for token-based enum resolution -------------------------

_ACCESS_MODE_TOKENS = [
    ("DYNAMIC", AccessMode.DYNAMIC),
    ("EXCLUSIVE", AccessMode.EXCLUSIVE),
    ("RANDOM", AccessMode.RANDOM),
    ("SEQUENTIAL", AccessMode.SEQUENTIAL),
]

_ORG_MODE_TOKENS = [
    ("INDEXED", OrganizationMode.INDEXED),
    ("RELATIVE", OrganizationMode.RELATIVE),
    ("SEQUENTIAL", OrganizationMode.SEQUENTIAL),
]

_ORG_TYPE_TOKENS = [
    ("BINARY", OrganizationClauseType.BINARY),
    ("LINE", OrganizationClauseType.LINE),
    ("RECORD", OrganizationClauseType.RECORD),
    ("RECORD_BINARY", OrganizationClauseType.RECORD_BINARY),
]

_ASSIGN_TOKENS = [
    ("CALL", AssignClauseType.CALL),
    ("DISK", AssignClauseType.DISK),
    ("DISPLAY", AssignClauseType.DISPLAY),
    ("KEYBOARD", AssignClauseType.KEYBOARD),
    ("PORT", AssignClauseType.PORT),
    ("PRINTER", AssignClauseType.PRINTER),
    ("READER", AssignClauseType.READER),
    ("REMOTE", AssignClauseType.REMOTE),
    ("TAPE", AssignClauseType.TAPE),
    ("VIRTUAL", AssignClauseType.VIRTUAL),
]

_DELIM_TOKENS = [
    ("ASSIGNMENT", RecordDelimiterClauseType.ASSIGNMENT),
    ("IMPLICIT", RecordDelimiterClauseType.IMPLICIT),
    ("STANDARD_1", RecordDelimiterClauseType.STANDARD_1),
]


def _dispatch(ctx, token_map):
    for token, value in token_map:
        if _has(ctx, token):
            return value
    return None


# -- sections / paragraphs ---------------------------------------------------

class ConfigurationSection(CobolDivisionElement):
    """CONFIGURATION SECTION: source-computer and object-computer paragraphs."""

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.source_computer_paragraph: Optional[SourceComputerParagraph] = None
        self.object_computer_paragraph: Optional[ObjectComputerParagraph] = None

    def add_source_computer_paragraph(self, ctx) -> "SourceComputerParagraph":
        result = self._get_element(ctx)
        if result is None:
            result = SourceComputerParagraph(self.program_unit, ctx)
            cn = ctx.computerName()
            if cn is not None:
                result.name = cn.getText()
            result.debugging = _has(ctx, "DEBUGGING")
            self.source_computer_paragraph = result
            self._register(result)
        return result

    def add_object_computer_paragraph(self, ctx) -> "ObjectComputerParagraph":
        result = self._get_element(ctx)
        if result is None:
            result = ObjectComputerParagraph(self.program_unit, ctx)
            cn = ctx.computerName()
            if cn is not None:
                result.name = cn.getText()
            for clause_ctx in (ctx.objectComputerClause() or []):
                if clause_ctx.memorySizeClause() is not None:
                    result.add_memory_size_clause(clause_ctx.memorySizeClause())
                elif clause_ctx.diskSizeClause() is not None:
                    result.add_disk_size_clause(clause_ctx.diskSizeClause())
                elif clause_ctx.collatingSequenceClause() is not None:
                    result.add_collating_sequence_clause(clause_ctx.collatingSequenceClause())
                elif clause_ctx.characterSetClause() is not None:
                    result.add_character_set_clause(clause_ctx.characterSetClause())
                elif clause_ctx.segmentLimitClause() is not None:
                    result.add_segment_limit_clause(clause_ctx.segmentLimitClause())
            self.object_computer_paragraph = result
            self._register(result)
        return result


# -- configuration section clause models -----------------------------------

class SourceComputerParagraph(CobolDivisionElement):
    """SOURCE-COMPUTER. <name> [WITH DEBUGGING MODE]."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name: Optional[str] = None
        self.debugging: bool = False


class ObjectComputerParagraph(CobolDivisionElement):
    """OBJECT-COMPUTER. <name> [clauses]."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name: Optional[str] = None
        self.memory_size_clause: Optional[MemorySizeClause] = None
        self.disk_size_clause: Optional[DiskSizeClause] = None
        self.collating_sequence_clause: Optional[CollatingSequenceClause] = None
        self.character_set_clause: Optional[CharacterSetClause] = None
        self.segment_limit_clause: Optional[SegmentLimitClause] = None

    def _make(self, cls, attr, ctx, **kw):
        result = self._get_element(ctx)
        if result is None:
            result = cls(self.program_unit, ctx)
            for k, v in kw.items():
                setattr(result, k, v)
            setattr(self, attr, result)
            self._register(result)
        return result

    def add_memory_size_clause(self, ctx) -> "MemorySizeClause":
        v = ctx.integerLiteral() or ctx.identifier()
        return self._make(MemorySizeClause, "memory_size_clause", ctx,
                          value=v.getText() if v else None)

    def add_disk_size_clause(self, ctx) -> "DiskSizeClause":
        v = ctx.integerLiteral() or ctx.identifier()
        return self._make(DiskSizeClause, "disk_size_clause", ctx,
                          value=v.getText() if v else None)

    def add_collating_sequence_clause(self, ctx) -> "CollatingSequenceClause":
        an = ctx.alphabetName()
        return self._make(CollatingSequenceClause, "collating_sequence_clause", ctx,
                          alphabet_name=an.getText() if an else None)

    def add_character_set_clause(self, ctx) -> "CharacterSetClause":
        an = ctx.alphabetName()
        return self._make(CharacterSetClause, "character_set_clause", ctx,
                          alphabet_name=an.getText() if an else None)

    def add_segment_limit_clause(self, ctx) -> "SegmentLimitClause":
        v = ctx.integerLiteral()
        return self._make(SegmentLimitClause, "segment_limit_clause", ctx,
                          limit=int(v.getText()) if v else None)


class CharacterSetClause(CobolDivisionElement):
    """CHARACTER SET <alphabet>."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.alphabet_name: Optional[str] = None


class CollatingSequenceClause(CobolDivisionElement):
    """COLLATING SEQUENCE IS <alphabet>."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.alphabet_name: Optional[str] = None


class DiskSizeClause(CobolDivisionElement):
    """DISK SIZE IS <size>."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.value: Optional[str] = None


class MemorySizeClause(CobolDivisionElement):
    """MEMORY SIZE IS <size>."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.value: Optional[str] = None


class SegmentLimitClause(CobolDivisionElement):
    """SEGMENT-LIMIT IS <limit>."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.limit: Optional[int] = None


# -- special-names paragraph + clause models (12 clauses) -------------------

class _SPFlag(CobolDivisionElement):
    """Boolean-valued special-name clause (just stores presence)."""
    def __init__(self, program_unit, ctx):
        super().__init__(program_unit=program_unit, ctx=ctx)


class AlphabetClause(CobolDivisionElement):
    """ALPHABET <name> IS STANDARD_1|STANDARD_2|NATIVE|EBCDIC|<chars>."""

    class AlphabetType(Enum):
        STANDARD_1 = "STANDARD_1"
        STANDARD_2 = "STANDARD_2"
        NATIVE = "NATIVE"
        EBCDIC = "EBCDIC"
        ALPHANUMERIC = "ALPHANUMERIC"
        NATIONAL = "NATIONAL"

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.alphabet_name: Optional[str] = None
        self.alphabet_type: Optional[AlphabetClause.AlphabetType] = None
        self.alphanumeric: Optional[AlphabetClauseAlphanumeric] = None
        self.national: Optional[AlphabetClauseNational] = None


class AlphabetClauseAlphanumeric(CobolDivisionElement):
    """ALPHABET <name> IS <chars>. Also used for literal character lists."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.alphabet_chars: Optional[str] = None


class AlphabetClauseNational(CobolDivisionElement):
    """ALPHABET <name> IS NATIONAL <chars>."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.national_chars: Optional[str] = None


class ChannelClause(CobolDivisionElement):
    """CHANNEL <id> IS <mnemonic>."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.channel_name: Optional[str] = None
        self.channel_call = None


class ClassThrough:
    """One THROUGH range in a CLASS clause."""

    __slots__ = ("from_call", "to_call")

    def __init__(self):
        self.from_call = None
        self.to_call = None


class ClassClause(CobolDivisionElement):
    """CLASS <name> IS <literal> [THROUGH <literal>]..."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.class_name: Optional[str] = None
        self.class_throughs: List[ClassThrough] = []


class CurrencySignClause(CobolDivisionElement):
    """CURRENCY SIGN IS <char> [WITH PICTURE SYMBOL <char>]."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.currency_sign: Optional[str] = None
        self.with_picture_symbol: Optional[str] = None


class DecimalPointClause(CobolDivisionElement):
    """DECIMAL-POINT IS COMMA."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.is_comma: bool = False


class DefaultDisplaySignClause(_SPFlag):
    """DEFAULT-DISPLAY-SIGN clause (boolean presence marker)."""


class OdtClause(_SPFlag):
    """ODT clause (boolean presence marker)."""


class ReserveNetworkClause(CobolDivisionElement):
    """RESERVE NETWORK clause."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.reserve_network: bool = False


class SymbolicCharacter:
    """One symbolic-character pair (integer, character-value)."""

    __slots__ = ("symbolic_char", "char_value")

    def __init__(self):
        self.symbolic_char: Optional[str] = None
        self.char_value: Optional[str] = None


class SymbolicCharactersClause(CobolDivisionElement):
    """SYMBOLIC CHARACTERS <pairs>..."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.symbolic_character_pairs: List[SymbolicCharacter] = []


class SpecialNamesParagraph(CobolDivisionElement):
    """SPECIAL-NAMES paragraph: alphabet, class, currency, decimal, etc."""

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.alphabet_clauses: List[AlphabetClause] = []
        self.channel_clauses: List[ChannelClause] = []
        self.class_clauses: List[ClassClause] = []
        self.currency_sign_clause: Optional[CurrencySignClause] = None
        self.decimal_point_clause: Optional[DecimalPointClause] = None
        self.default_display_sign_clause: Optional[DefaultDisplaySignClause] = None
        self.odt_clause: Optional[OdtClause] = None
        self.reserve_network_clause: Optional[ReserveNetworkClause] = None
        self.symbolic_characters_clause: Optional[SymbolicCharactersClause] = None

    def add_alphabet_clause(self, ctx) -> AlphabetClause:
        result = self._get_element(ctx)
        if result is None:
            result = AlphabetClause(self.program_unit, ctx)
            # The grammar nests alphabetName inside format1/format2
            fmt1 = ctx.alphabetClauseFormat1()
            fmt2 = ctx.alphabetClauseFormat2()
            sub = fmt1 or fmt2
            if sub is not None:
                an = getattr(sub, "alphabetName", lambda: None)()
                if an is not None:
                    result.alphabet_name = an.getText()
            AT = AlphabetClause.AlphabetType
            if _has(ctx, "STANDARD_2"):
                result.alphabet_type = AT.STANDARD_2
            elif _has(ctx, "STANDARD_1"):
                result.alphabet_type = AT.STANDARD_1
            elif _has(ctx, "NATIVE"):
                result.alphabet_type = AT.NATIVE
            elif _has(ctx, "EBCDIC"):
                result.alphabet_type = AT.EBCDIC
            self.alphabet_clauses.append(result)
            self._register(result)
        return result

    def add_channel_clause(self, ctx) -> ChannelClause:
        result = self._get_element(ctx)
        if result is None:
            result = ChannelClause(self.program_unit, ctx)
            il = ctx.integerLiteral()
            if il is not None:
                result.channel_name = il.getText()
            mn = ctx.mnemonicName()
            if mn is not None:
                result.channel_call = self.create_call(mn)
            self.channel_clauses.append(result)
            self._register(result)
        return result

    def add_class_clause(self, ctx) -> ClassClause:
        result = self._get_element(ctx)
        if result is None:
            result = ClassClause(self.program_unit, ctx)
            cn = ctx.className()
            if cn is not None:
                result.class_name = cn.getText()
            for ct in ctx.classThrough():
                ct_obj = ClassThrough()
                ils = ct.literal()
                if len(ils) >= 1:
                    ct_obj.from_call = ils[0].getText()
                if len(ils) >= 2:
                    ct_obj.to_call = ils[1].getText()
                result.class_throughs.append(ct_obj)
            self.class_clauses.append(result)
            self._register(result)
        return result

    def add_currency_sign_clause(self, ctx) -> CurrencySignClause:
        result = self._get_element(ctx)
        if result is None:
            result = CurrencySignClause(self.program_unit, ctx)
            lits = ctx.literal()
            if lits:
                result.currency_sign = lits[0].getText()
                if len(lits) > 1:
                    result.with_picture_symbol = lits[1].getText()
            self.currency_sign_clause = result
            self._register(result)
        return result

    def add_decimal_point_clause(self, ctx) -> DecimalPointClause:
        result = self._get_element(ctx)
        if result is None:
            result = DecimalPointClause(self.program_unit, ctx)
            result.is_comma = _has(ctx, "COMMA")
            self.decimal_point_clause = result
            self._register(result)
        return result

    def add_default_display_sign_clause(self, ctx) -> DefaultDisplaySignClause:
        return self._add_flag(DefaultDisplaySignClause, "default_display_sign_clause", ctx)

    def add_odt_clause(self, ctx) -> OdtClause:
        return self._add_flag(OdtClause, "odt_clause", ctx)

    def add_reserve_network_clause(self, ctx) -> ReserveNetworkClause:
        result = self._get_element(ctx)
        if result is None:
            result = ReserveNetworkClause(self.program_unit, ctx)
            result.reserve_network = True
            self.reserve_network_clause = result
            self._register(result)
        return result

    def add_symbolic_characters_clause(self, ctx) -> SymbolicCharactersClause:
        result = self._get_element(ctx)
        if result is None:
            result = SymbolicCharactersClause(self.program_unit, ctx)
            for sc_ctx in ctx.symbolicCharacter():
                sc = SymbolicCharacter()
                sc.symbolic_char = sc_ctx.symbolicCharacterName().getText()
                ils = sc_ctx.integerLiteral()
                if ils:
                    sc.char_value = ils.getText()
                result.symbolic_character_pairs.append(sc)
            self.symbolic_characters_clause = result
            self._register(result)
        return result

    def _add_flag(self, cls, attr, ctx):
        result = self._get_element(ctx)
        if result is None:
            result = cls(self.program_unit, ctx)
            setattr(self, attr, result)
            self._register(result)
        return result


# -- I-O control paragraph + clause models (7 clauses) -----------------------

class CommitmentControlClause(CobolDivisionElement):
    """COMMITMENT CONTROL clause."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.commitment_control: bool = False


class MultipleFilePosition:
    """One POSITION <pos> FILE <file> pair within SAME/MULTIPLE FILE."""

    __slots__ = ("position_call", "file_call")

    def __init__(self):
        self.position_call = None
        self.file_call = None


class MultipleFileClause(CobolDivisionElement):
    """MULTIPLE FILE TAPE CONTAINS <files> [POSITION <pos>]."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.file_calls: List = []
        self.positions: List[MultipleFilePosition] = []


class RerunEveryClock(CobolDivisionElement):
    """RERUN EVERY <clock>."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.clock_value: Optional[str] = None


class RerunEveryOf(CobolDivisionElement):
    """RERUN EVERY <of>."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.of_value: Optional[str] = None


class RerunEveryRecords(CobolDivisionElement):
    """RERUN EVERY <records>."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.records_value: Optional[str] = None


class RerunClause(CobolDivisionElement):
    """RERUN ON <file> EVERY (CLOCK <v> | <v> RECORDS | END OF <unit> OF <file>)."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.rerun_call = None
        self.every_clock: Optional[RerunEveryClock] = None
        self.every_of: Optional[RerunEveryOf] = None
        self.every_records: Optional[RerunEveryRecords] = None


class SameClause(CobolDivisionElement):
    """SAME RECORD|SORT|SORT-MERGE AREA FOR <files>."""

    def __init__(self, program_unit, ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.same_type: Optional[str] = None  # RECORD, SORT, SORT_MERGE
        self.file_calls: List = []


class IoControlParagraph(CobolDivisionElement):
    """I-O-CONTROL paragraph: rerun, same, multiple file clauses."""

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.commitment_control_clause: Optional[CommitmentControlClause] = None
        self.multiple_file_clause: Optional[MultipleFileClause] = None
        self.rerun_clause: Optional[RerunClause] = None
        self.same_clauses: List[SameClause] = []

    def _make(self, cls, attr, ctx, **kw):
        result = self._get_element(ctx)
        if result is None:
            result = cls(self.program_unit, ctx)
            for k, v in kw.items():
                setattr(result, k, v)
            setattr(self, attr, result)
            self._register(result)
        return result

    def add_commitment_control_clause(self, ctx) -> CommitmentControlClause:
        return self._make(CommitmentControlClause, "commitment_control_clause", ctx,
                          commitment_control=True)

    def add_multiple_file_clause(self, ctx) -> MultipleFileClause:
        result = self._get_element(ctx)
        if result is None:
            result = MultipleFileClause(self.program_unit, ctx)
            for fn in ctx.fileName():
                result.file_calls.append(self.create_call(fn))
            for mp in ctx.multipleFilePosition():
                pos = MultipleFilePosition()
                il = mp.integerLiteral()
                if il is not None:
                    pos.position_call = il.getText()
                fn2 = mp.fileName()
                if fn2 is not None:
                    pos.file_call = self.create_call(fn2)
                result.positions.append(pos)
            self.multiple_file_clause = result
            self._register(result)
        return result

    def add_rerun_clause(self, ctx) -> RerunClause:
        result = self._get_element(ctx)
        if result is None:
            result = RerunClause(self.program_unit, ctx)
            fn = ctx.fileName()
            if fn is not None:
                result.rerun_call = self.create_call(fn)
            ec = ctx.rerunEveryClock()
            if ec is not None:
                ev = RerunEveryClock(self.program_unit, ec)
                ev.clock_value = ec.getText()
                result.every_clock = ev
            eo = ctx.rerunEveryOf()
            if eo is not None:
                ev = RerunEveryOf(self.program_unit, eo)
                ev.of_value = eo.getText()
                result.every_of = ev
            er = ctx.rerunEveryRecords()
            if er is not None:
                ev = RerunEveryRecords(self.program_unit, er)
                ev.records_value = er.getText()
                result.every_records = ev
            self.rerun_clause = result
            self._register(result)
        return result

    def add_same_clause(self, ctx) -> SameClause:
        result = self._get_element(ctx)
        if result is None:
            result = SameClause(self.program_unit, ctx)
            if _has(ctx, "SORT_MERGE"):
                result.same_type = "SORT_MERGE"
            elif _has(ctx, "SORT"):
                result.same_type = "SORT"
            elif _has(ctx, "RECORD"):
                result.same_type = "RECORD"
            for fn in ctx.fileName():
                result.file_calls.append(self.create_call(fn))
            self.same_clauses.append(result)
            self._register(result)
        return result


class FileControlEntry(CobolDivisionElement, NamedElement):
    """One ``SELECT`` statement: a file-name + its sub-clauses.

    Ports ``FileControlEntry`` interface. Each SELECT clause (Assign, AccessMode,
    Organization, ...) is stored as a typed ASG element, built lazily via
    ``add_<clause>(ctx)`` factory methods.
    """

    def __init__(self, name, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.name = name
        self.calls: List = []  # FileControlEntryCall
        self.file_description_entry: "Optional[FileDescriptionEntry]" = None

        # -- clause storage (one per clause type) ---
        self.select_clause: Optional[SelectClause] = None
        self.assign_clause: Optional[AssignClause] = None
        self.access_mode_clause: Optional[AccessModeClause] = None
        self.organization_clause: Optional[OrganizationClause] = None
        self.file_status_clause: Optional[FileStatusClause] = None
        self.password_clause: Optional[PasswordClause] = None
        self.record_key_clause: Optional[RecordKeyClause] = None
        self.alternate_record_key_clause: Optional[AlternateRecordKeyClause] = None
        self.relative_key_clause: Optional[RelativeKeyClause] = None
        self.padding_character_clause: Optional[PaddingCharacterClause] = None
        self.record_delimiter_clause: Optional[RecordDelimiterClause] = None
        self.reserve_clause: Optional[ReserveClause] = None
        self._alternate_record_key_clauses: List[AlternateRecordKeyClause] = []

    def add_call(self, call) -> None:
        self.calls.append(call)

    # -- clause builders ------------------------------------------------------

    def add_select_clause(self, ctx) -> SelectClause:
        result = self._get_element(ctx)
        if result is None:
            result = SelectClause(self.program_unit, ctx)
            result.name = self.determine_name(ctx)
            result.optional = _has(ctx, "OPTIONAL")
            fn = ctx.fileName()
            if fn is not None:
                result.file_call = self.create_call(fn)
            self.select_clause = result
            self._register(result)
        return result

    def add_assign_clause(self, ctx) -> AssignClause:
        result = self._get_element(ctx)
        if result is None:
            result = AssignClause(self.program_unit, ctx)
            result.assign_clause_type = _dispatch(ctx, _ASSIGN_TOKENS)
            asn = ctx.assignmentName()
            lit = ctx.literal()
            if asn is not None:
                result.to_value_stmt = self.create_value_stmt(asn)
            elif lit is not None:
                result.to_value_stmt = self.create_value_stmt(lit)
            self.assign_clause = result
            self._register(result)
        return result

    def add_access_mode_clause(self, ctx) -> AccessModeClause:
        result = self._get_element(ctx)
        if result is None:
            result = AccessModeClause(self.program_unit, ctx)
            result.mode = _dispatch(ctx, _ACCESS_MODE_TOKENS)
            self.access_mode_clause = result
            self._register(result)
        return result

    def add_organization_clause(self, ctx) -> OrganizationClause:
        result = self._get_element(ctx)
        if result is None:
            result = OrganizationClause(self.program_unit, ctx)
            result.mode = _dispatch(ctx, _ORG_MODE_TOKENS)
            result.organization_clause_type = _dispatch(ctx, _ORG_TYPE_TOKENS)
            self.organization_clause = result
            self._register(result)
        return result

    def add_file_status_clause(self, ctx) -> FileStatusClause:
        result = self._get_element(ctx)
        if result is None:
            result = FileStatusClause(self.program_unit, ctx)
            qdns = ctx.qualifiedDataName()
            if qdns:
                result.data_call = self.create_call(qdns[0])
                if len(qdns) > 1:
                    result.data_call2 = self.create_call(qdns[1])
            self.file_status_clause = result
            self._register(result)
        return result

    def add_password_clause(self, ctx) -> PasswordClause:
        result = self._get_element(ctx)
        if result is None:
            result = PasswordClause(self.program_unit, ctx)
            dn = ctx.dataName()
            if dn is not None:
                result.data_call = self.create_call(dn)
            self.password_clause = result
            self._register(result)
        return result

    def add_record_key_clause(self, ctx) -> RecordKeyClause:
        result = self._get_element(ctx)
        if result is None:
            result = RecordKeyClause(self.program_unit, ctx)
            qdn = ctx.qualifiedDataName()
            if qdn is not None:
                result.record_key_call = self.create_call(qdn)
            pwd = ctx.passwordClause()
            if pwd is not None:
                result.password_clause = self.add_password_clause(pwd)
            self.record_key_clause = result
            self._register(result)
        return result

    def add_alternate_record_key_clause(self, ctx) -> AlternateRecordKeyClause:
        result = self._get_element(ctx)
        if result is None:
            result = AlternateRecordKeyClause(self.program_unit, ctx)
            qdn = ctx.qualifiedDataName()
            if qdn is not None:
                result.data_call = self.create_call(qdn)
            pwd = ctx.passwordClause()
            if pwd is not None:
                result.password_clause = self.add_password_clause(pwd)
            self._alternate_record_key_clauses.append(result)
            self._register(result)
        return result

    @property
    def alternate_record_key_clauses(self) -> List[AlternateRecordKeyClause]:
        return self._alternate_record_key_clauses

    def add_relative_key_clause(self, ctx) -> RelativeKeyClause:
        result = self._get_element(ctx)
        if result is None:
            result = RelativeKeyClause(self.program_unit, ctx)
            qdn = ctx.qualifiedDataName()
            if qdn is not None:
                result.relative_key_call = self.create_call(qdn)
            self.relative_key_clause = result
            self._register(result)
        return result

    def add_padding_character_clause(self, ctx) -> PaddingCharacterClause:
        result = self._get_element(ctx)
        if result is None:
            result = PaddingCharacterClause(self.program_unit, ctx)
            ident = ctx.identifier()
            lit = ctx.literal()
            if ident is not None or lit is not None:
                result.value_stmt = self.create_value_stmt(ident, lit)
            self.padding_character_clause = result
            self._register(result)
        return result

    def add_record_delimiter_clause(self, ctx) -> RecordDelimiterClause:
        result = self._get_element(ctx)
        if result is None:
            result = RecordDelimiterClause(self.program_unit, ctx)
            result.record_delimiter_clause_type = _dispatch(ctx, _DELIM_TOKENS)
            ident = ctx.identifier()
            lit = ctx.literal()
            if ident is not None or lit is not None:
                result.value_stmt = self.create_value_stmt(ident, lit)
            self.record_delimiter_clause = result
            self._register(result)
        return result

    def add_reserve_clause(self, ctx) -> ReserveClause:
        result = self._get_element(ctx)
        if result is None:
            result = ReserveClause(self.program_unit, ctx)
            il = ctx.integerLiteral()
            if il is not None:
                result.value_stmt = self.create_value_stmt(il)
            self.reserve_clause = result
            self._register(result)
        return result


class FileControlParagraph(CobolDivisionElement):
    """The FILE-CONTROL paragraph: holds the SELECT entries."""

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self._entries: List[FileControlEntry] = []
        self._by_name: Dict[Optional[str], List[FileControlEntry]] = {}

    def add_file_control_entry(self, ctx) -> FileControlEntry:
        result = self._get_element(ctx)
        if result is None:
            name = self.determine_name(ctx)
            result = FileControlEntry(name, self.program_unit, ctx)
            self._populate_entry(result, ctx)
            self._entries.append(result)
            self._by_name.setdefault(_symbol(name), []).append(result)
            self._register(result)
        return result

    @staticmethod
    def _populate_entry(entry: FileControlEntry, ctx) -> None:
        """Populate clauses from the fileControlEntry context.

        Sub-clauses (accessMode, organization, assign, ...) are visited by the
        CobolFileControlClauseVisitor pass, which calls entry.add_* directly.
        For now the select clause is handled inline.
        """
        # Select clause: file name + OPTIONAL flag
        sc = ctx.selectClause()
        if sc is not None:
            entry.add_select_clause(sc)

        # Walk fileControlClause children for the remaining clauses.
        # Each clause visitor (from CobolVisitor.py) calls entry.add_<clause>(ctx).
        for clause_ctx in (ctx.fileControlClause() or []):
            if clause_ctx.assignClause() is not None:
                entry.add_assign_clause(clause_ctx.assignClause())
            elif clause_ctx.organizationClause() is not None:
                entry.add_organization_clause(clause_ctx.organizationClause())
            elif clause_ctx.accessModeClause() is not None:
                entry.add_access_mode_clause(clause_ctx.accessModeClause())
            elif clause_ctx.fileStatusClause() is not None:
                entry.add_file_status_clause(clause_ctx.fileStatusClause())
            elif clause_ctx.passwordClause() is not None:
                entry.add_password_clause(clause_ctx.passwordClause())
            elif clause_ctx.recordKeyClause() is not None:
                entry.add_record_key_clause(clause_ctx.recordKeyClause())
            elif clause_ctx.alternateRecordKeyClause() is not None:
                entry.add_alternate_record_key_clause(clause_ctx.alternateRecordKeyClause())
            elif clause_ctx.relativeKeyClause() is not None:
                entry.add_relative_key_clause(clause_ctx.relativeKeyClause())
            elif clause_ctx.paddingCharacterClause() is not None:
                entry.add_padding_character_clause(clause_ctx.paddingCharacterClause())
            elif clause_ctx.recordDelimiterClause() is not None:
                entry.add_record_delimiter_clause(clause_ctx.recordDelimiterClause())
            elif clause_ctx.reserveClause() is not None:
                entry.add_reserve_clause(clause_ctx.reserveClause())

    @property
    def file_control_entries(self) -> List[FileControlEntry]:
        return self._entries

    def get_file_control_entry(self, name: str) -> Optional[FileControlEntry]:
        entries = self._by_name.get(_symbol(name), [])
        return entries[0] if entries else None


class InputOutputSection(CobolDivisionElement):
    """INPUT-OUTPUT SECTION: file-control + i-o-control paragraphs."""

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.file_control_paragraph: Optional[FileControlParagraph] = None
        self.io_control_paragraph: Optional[IoControlParagraph] = None

    def add_file_control_paragraph(self, ctx) -> FileControlParagraph:
        result = self._get_element(ctx)
        if result is None:
            result = FileControlParagraph(self.program_unit, ctx)
            for entry_ctx in ctx.fileControlEntry():
                result.add_file_control_entry(entry_ctx)
            self.file_control_paragraph = result
            self._register(result)
        return result

    def add_io_control_paragraph(self, ctx) -> IoControlParagraph:
        result = self._get_element(ctx)
        if result is None:
            result = IoControlParagraph(self.program_unit, ctx)
            for clause in (ctx.ioControlClause() or []):
                if clause.commitmentControlClause() is not None:
                    result.add_commitment_control_clause(clause.commitmentControlClause())
                elif clause.multipleFileClause() is not None:
                    result.add_multiple_file_clause(clause.multipleFileClause())
                elif clause.rerunClause() is not None:
                    result.add_rerun_clause(clause.rerunClause())
                elif clause.sameClause() is not None:
                    result.add_same_clause(clause.sameClause())
            self.io_control_paragraph = result
            self._register(result)
        return result


class EnvironmentDivision(CobolDivisionElement):
    """ENVIRONMENT DIVISION: configuration, input-output, special-names."""

    def __init__(self, program_unit: "ProgramUnit", ctx: ParserRuleContext) -> None:
        super().__init__(program_unit=program_unit, ctx=ctx)
        self.configuration_section: Optional[ConfigurationSection] = None
        self.input_output_section: Optional[InputOutputSection] = None
        self.special_names_paragraph: Optional[SpecialNamesParagraph] = None

    def add_configuration_section(self, ctx) -> ConfigurationSection:
        result = self._get_element(ctx)
        if result is None:
            result = ConfigurationSection(self.program_unit, ctx)
            self.configuration_section = result
            self._register(result)
        return result

    def add_special_names_paragraph(self, ctx) -> SpecialNamesParagraph:
        result = self._get_element(ctx)
        if result is None:
            result = SpecialNamesParagraph(self.program_unit, ctx)
            self.special_names_paragraph = result
            self._register(result)
        return result

    def add_input_output_section(self, ctx) -> InputOutputSection:
        result = self._get_element(ctx)
        if result is None:
            result = InputOutputSection(self.program_unit, ctx)
            for paragraph_ctx in ctx.inputOutputSectionParagraph():
                if paragraph_ctx.fileControlParagraph() is not None:
                    result.add_file_control_paragraph(paragraph_ctx.fileControlParagraph())
                elif paragraph_ctx.ioControlParagraph() is not None:
                    result.add_io_control_paragraph(paragraph_ctx.ioControlParagraph())
            self.input_output_section = result
            self._register(result)
        return result
