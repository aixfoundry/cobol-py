"""Disk resolution of COPY copybooks.

Ports the three proleap finders in ``preprocessor.sub.copybook.impl``:

* :class:`CobolWordCopyBookFinderImpl` - ``COPY BOOK1`` (identifier lookup by
  name + extension).
* :class:`LiteralCopyBookFinderImpl` - ``COPY "path/to/book"`` (quotes stripped,
  resolved absolute-then-relative against the copy dir).
* :class:`FilenameCopyBookFinderImpl` - ``COPY <filename>`` (raw text path).

``java.io.File`` maps to :class:`pathlib.Path`; absolute/normalize semantics use
``os.path.abspath`` + ``os.path.normpath`` (Java ``getAbsolutePath`` + ``normalize``).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from ..params import CobolParserParams
from ..util.filename_utils import get_base_name
from .string_utils import trim_quotes

_LOG = logging.getLogger(__name__)


def _norm(path) -> str:
    """Java ``Paths.get(getAbsolutePath(path)).normalize()`` equivalent."""
    return os.path.normpath(os.path.abspath(str(path)))


# --- COPY <cobol-word> -------------------------------------------------------


class CobolWordCopyBookFinderImpl:
    def find_copy_book(self, params: CobolParserParams, ctx) -> Optional[Path]:
        # Fast path: O(1) lookup via pre-built name index.
        if params.copybook_name_index is not None:
            identifier = ctx.getText().lower()
            if params.copy_book_extensions is not None:
                for ext in params.copy_book_extensions:
                    key = identifier + "." + ext if ext else identifier
                    result = params.copybook_name_index.get(key)
                    if result is not None:
                        return result
            else:
                result = params.copybook_name_index.get(identifier)
                if result is not None:
                    return result

        # Slow path: linear scan (backward compatible).
        if params.copy_book_files is not None:
            for copy_book_file in params.copy_book_files:
                if self._is_matching_copy_book(copy_book_file, params, ctx):
                    return copy_book_file

        if params.copy_book_directories is not None:
            for copy_book_directory in params.copy_book_directories:
                valid = self._find_copy_book_in_directory(copy_book_directory, params, ctx)
                if valid is not None:
                    return valid

        return None

    def _find_copy_book_in_directory(
        self, copy_books_directory: Path, params: CobolParserParams, ctx
    ) -> Optional[Path]:
        if not copy_books_directory.is_dir():
            return None
        try:
            for copy_book_candidate in copy_books_directory.rglob("*"):
                if copy_book_candidate.is_file() and self._is_matching_copy_book(
                    copy_book_candidate, params, ctx
                ):
                    return copy_book_candidate
        except OSError as e:  # pragma: no cover - filesystem dependent
            _LOG.warning("%s", e)
        return None

    def _is_matching_copy_book(
        self, copy_book_candidate: Path, params: CobolParserParams, ctx
    ) -> bool:
        copy_book_identifier = ctx.getText()

        if params.copy_book_extensions is not None:
            for copy_book_extension in params.copy_book_extensions:
                if self._is_matching_copy_book_with_extension(
                    copy_book_candidate, copy_book_identifier, copy_book_extension
                ):
                    return True
            return False
        return self._is_matching_copy_book_without_extension(
            copy_book_candidate, copy_book_identifier
        )

    @staticmethod
    def _is_matching_copy_book_with_extension(
        copy_book_candidate: Path, copy_book_identifier: str, copy_book_extension: str
    ) -> bool:
        copy_book_filename = (
            copy_book_identifier
            if (copy_book_extension is None or copy_book_extension == "")
            else copy_book_identifier + "." + copy_book_extension
        )
        return copy_book_filename.lower() == copy_book_candidate.name.lower()

    @staticmethod
    def _is_matching_copy_book_without_extension(
        copy_book_candidate: Path, copy_book_identifier: str
    ) -> bool:
        copy_book_candidate_base_name = get_base_name(copy_book_candidate.name)
        return copy_book_candidate_base_name.lower() == copy_book_identifier.lower()


# --- COPY "literal" ----------------------------------------------------------


class LiteralCopyBookFinderImpl:
    def find_copy_book(self, params: CobolParserParams, ctx) -> Optional[Path]:
        # Fast path: O(1) lookup via pre-built name index.
        if params.copybook_name_index is not None:
            copy_book_identifier = trim_quotes(ctx.getText()).replace("\\", "/")
            result = params.copybook_name_index.get(copy_book_identifier.lower())
            if result is not None:
                return result
            # Also try basename (handle path-containing identifiers like "dir/NAME.INC").
            basename = copy_book_identifier.split("/")[-1].lower()
            if basename != copy_book_identifier.lower():
                result = params.copybook_name_index.get(basename)
                if result is not None:
                    return result

        # Slow path: linear scan (backward compatible).
        if params.copy_book_files is not None:
            for copy_book_file in params.copy_book_files:
                if self._is_matching_copy_book(copy_book_file, None, ctx):
                    return copy_book_file

        if params.copy_book_directories is not None:
            for copy_book_directory in params.copy_book_directories:
                valid = self._find_copy_book_in_directory(copy_book_directory, ctx)
                if valid is not None:
                    return valid

        return None

    def _find_copy_book_in_directory(
        self, copy_books_directory: Path, ctx
    ) -> Optional[Path]:
        if not copy_books_directory.is_dir():
            return None
        try:
            for copy_book_candidate in copy_books_directory.rglob("*"):
                if self._is_matching_copy_book(copy_book_candidate, copy_books_directory, ctx):
                    return copy_book_candidate
        except OSError as e:  # pragma: no cover - filesystem dependent
            _LOG.warning("%s", e)
        return None

    def _is_matching_copy_book(
        self, copy_book_candidate: Path, cobol_copy_dir: Optional[Path], ctx
    ) -> bool:
        copy_book_identifier = trim_quotes(ctx.getText()).replace("\\", "/")
        if cobol_copy_dir is None:
            return self._is_matching_copy_book_relative(copy_book_candidate, copy_book_identifier)
        return self._is_matching_copy_book_absolute(
            copy_book_candidate, cobol_copy_dir, copy_book_identifier
        )

    @staticmethod
    def _is_matching_copy_book_absolute(
        copy_book_candidate: Path, cobol_copy_dir: Path, copy_book_identifier: str
    ) -> bool:
        candidate_abs = _norm(copy_book_candidate)
        identifier_abs = os.path.normpath(
            os.path.join(os.path.abspath(str(cobol_copy_dir)), copy_book_identifier)
        )
        return identifier_abs.lower() == candidate_abs.lower()

    @staticmethod
    def _is_matching_copy_book_relative(
        copy_book_candidate: Path, copy_book_identifier: str
    ) -> bool:
        candidate_abs = _norm(copy_book_candidate)
        if (
            copy_book_identifier.startswith("/")
            or copy_book_identifier.startswith("./")
            or copy_book_identifier.startswith("\\")
            or copy_book_identifier.startswith(".\\")
        ):
            identifier_rel = os.path.normpath(copy_book_identifier)
        else:
            identifier_rel = os.path.normpath("/" + copy_book_identifier)
        return candidate_abs.lower().endswith(identifier_rel.lower())


# --- COPY <filename> ---------------------------------------------------------


class FilenameCopyBookFinderImpl:
    def find_copy_book(self, params: CobolParserParams, ctx) -> Optional[Path]:
        if params.copy_book_files is not None:
            for copy_book_file in params.copy_book_files:
                if self._is_matching_copy_book(copy_book_file, None, ctx):
                    return copy_book_file

        if params.copy_book_directories is not None:
            for copy_book_directory in params.copy_book_directories:
                valid = self._find_copy_book_in_directory(copy_book_directory, ctx)
                if valid is not None:
                    return valid

        return None

    def _find_copy_book_in_directory(
        self, copy_books_directory: Path, ctx
    ) -> Optional[Path]:
        if not copy_books_directory.is_dir():
            return None
        try:
            for copy_book_candidate in copy_books_directory.rglob("*"):
                if self._is_matching_copy_book(copy_book_candidate, copy_books_directory, ctx):
                    return copy_book_candidate
        except OSError as e:  # pragma: no cover - filesystem dependent
            _LOG.warning("%s", e)
        return None

    def _is_matching_copy_book(
        self, copy_book_candidate: Path, cobol_copy_dir: Optional[Path], ctx
    ) -> bool:
        copy_book_identifier = ctx.getText()
        if cobol_copy_dir is None:
            return self._is_matching_copy_book_relative(copy_book_candidate, copy_book_identifier)
        return self._is_matching_copy_book_absolute(
            copy_book_candidate, cobol_copy_dir, copy_book_identifier
        )

    @staticmethod
    def _is_matching_copy_book_absolute(
        copy_book_candidate: Path, cobol_copy_dir: Path, copy_book_identifier: str
    ) -> bool:
        candidate_abs = _norm(copy_book_candidate)
        identifier_abs = os.path.normpath(
            os.path.join(os.path.abspath(str(cobol_copy_dir)), copy_book_identifier)
        )
        return identifier_abs.lower() == candidate_abs.lower()

    @staticmethod
    def _is_matching_copy_book_relative(
        copy_book_candidate: Path, copy_book_identifier: str
    ) -> bool:
        candidate_abs = _norm(copy_book_candidate)
        identifier_rel = os.path.normpath("/" + copy_book_identifier)
        return candidate_abs.lower().endswith(identifier_rel.lower())
