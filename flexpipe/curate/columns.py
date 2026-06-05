"""
Column harmonization and dropping.

Provides:
- ``harmonize_column``: fills empty ``dst`` values from ``src``, then drops ``src``.
- ``drop_columns``: removes any column in the DROP set that is present in the DataFrame.
- ``DROP``: the canonical set of columns to discard from Pathoplexus/NCBI/ITpS metadata.

Extracted from ``scripts/curate.py`` (the ``_merge`` closure and the ``DROP`` set,
lines 312–393).
"""

import logging

import pandas as pd

from flexpipe.data import load_data_yaml

logger = logging.getLogger(__name__)


def _load_drop_set() -> set[str]:
    data = load_data_yaml("flexpipe.data.curation", "drop_columns.yaml")
    return set(data.get("drop", []))  # type: ignore[arg-type]


def harmonize_column(df: pd.DataFrame, src: str, dst: str) -> pd.DataFrame:
    """Fill empty *dst* values from *src*, then drop *src*.

    This implements the ``_merge`` pattern in the original curate.py: when the
    same semantic field has two names (e.g. Pathoplexus ``hostNameCommon`` and
    curated ``host``), the Pathoplexus name is merged into the canonical name
    and then removed.

    Args:
        df: Input DataFrame.
        src: Source column name (to merge from and then drop).
        dst: Destination column name (filled where currently empty/whitespace).

    Returns:
        DataFrame with *src* merged into *dst* and *src* dropped (in-place mutation
        on a copy is avoided; the returned object may be the same reference).
    """
    if src not in df.columns:
        return df
    if dst not in df.columns:
        df[dst] = ""
    src_vals = df[src].fillna("")
    dst_vals = df[dst].fillna("")
    df[dst] = dst_vals.where(dst_vals.str.strip() != "", src_vals)
    df.drop(columns=[src], inplace=True)
    return df


# Mapping of (src_column, dst_column) pairs for the PPX → canonical harmonization.
# Columns are renamed in this order; the same dst may appear multiple times
# (the second src fills values still empty after the first).
HARMONIZE_PAIRS = [
    ("hostNameCommon", "host"),
    ("hostGender", "sex"),
    ("hostAge", "age"),
    ("author", "authors"),
    ("authorAffiliations", "affiliations"),
    ("specimenCollectorSampleId", "sample_id"),
    ("specimen_id", "sample_id"),
    ("depthOfCoverage", "depth_of_coverage"),
    ("sampleType", "sample_type"),
    ("sequencingInstrument", "seq_instrument"),
    ("sequencingProtocol", "seq_tech"),
]


def apply_harmonization(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all standard PPX→canonical column harmonizations to *df*.

    Processes every pair in ``HARMONIZE_PAIRS`` in order.

    Args:
        df: Curated metadata DataFrame (modified in place).

    Returns:
        The same DataFrame with harmonized columns.
    """
    for src, dst in HARMONIZE_PAIRS:
        df = harmonize_column(df, src, dst)
    return df


# ── Columns to drop (loaded from flexpipe/data/curation/drop_columns.yaml) ───

DROP: set[str] = _load_drop_set()


def drop_columns(df: pd.DataFrame, drop_set: set[str] = DROP) -> pd.DataFrame:
    """Drop any column in *drop_set* that is present in *df*.

    Args:
        df: Input DataFrame.
        drop_set: Set of column names to remove (default: the canonical ``DROP`` set).

    Returns:
        DataFrame with the specified columns removed.
    """
    to_drop = [c for c in drop_set if c in df.columns]
    if to_drop:
        df.drop(columns=to_drop, inplace=True)
        logger.debug("Dropped %d columns", len(to_drop))
    return df
