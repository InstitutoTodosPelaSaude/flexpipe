"""
Clade truncation utility.

Extracted verbatim from ``scripts/curate.py`` ``truncate_clade`` (line 204).
"""

import logging

logger = logging.getLogger(__name__)


def truncate_clade(clade: str, levels: int, sep: str = ".") -> str:
    """Truncate a hierarchical clade name to *levels* levels.

    Examples::

        truncate_clade("A.B.C.D", 2)   # → "A.B"
        truncate_clade("I",        1)   # → "I"
        truncate_clade("",         1)   # → ""
        truncate_clade("A",        3)   # → "A"   (fewer parts than levels → keep all)

    Args:
        clade: Hierarchical clade string (e.g. ``"A.B.C.D"``).
        levels: Number of hierarchy levels to keep.
        sep: Separator character (default ``"."``).

    Returns:
        Truncated clade string, or ``""`` for empty/whitespace-only input.
    """
    parts = [p for p in str(clade).strip().split(sep) if p]
    return sep.join(parts[:levels]) if parts else ""
