"""COBOL preprocessor sub-package.

Public types are re-exported from :mod:`cobol_py` once the full pipeline is
assembled; import submodules directly for internal wiring.
"""

from __future__ import annotations

from .constants import CobolSourceFormatEnum, detect_source_format
