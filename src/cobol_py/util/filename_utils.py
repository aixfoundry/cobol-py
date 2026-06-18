"""Filename helpers.

Ports ``io.proleap.cobol.asg.util.FilenameUtils``. Behaves like the original
(which itself mimics Apache Commons IO): separators are both ``/`` and ``\\``,
the extension is the substring after the final ``.`` unless a separator follows
it.
"""

from __future__ import annotations

from typing import Optional


def _index_of_last_separator(filename: Optional[str]) -> int:
    if filename is None:
        return -1
    last_unix = filename.rfind("/")
    last_windows = filename.rfind("\\")
    return max(last_unix, last_windows)


def _index_of_extension(filename: Optional[str]) -> int:
    if filename is None:
        return -1
    extension_pos = filename.rfind(".")
    last_separator = _index_of_last_separator(filename)
    return -1 if last_separator > extension_pos else extension_pos


def get_base_name(filename: Optional[str]) -> Optional[str]:
    return remove_extension(get_name(filename))


def get_extension(filename: Optional[str]) -> Optional[str]:
    if filename is None:
        return None
    index = _index_of_extension(filename)
    return "" if index == -1 else filename[index + 1:]


def get_name(filename: Optional[str]) -> Optional[str]:
    if filename is None:
        return None
    index = _index_of_last_separator(filename)
    return filename[index + 1:]


def remove_extension(filename: Optional[str]) -> Optional[str]:
    if filename is None:
        return None
    index = _index_of_extension(filename)
    return filename if index == -1 else filename[:index]
