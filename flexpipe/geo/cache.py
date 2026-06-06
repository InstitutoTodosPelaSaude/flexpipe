"""
Coordinate cache management.

Provides ``merge_coordinate_cache`` which merges newly geocoded coordinates
into the workdir's persistent cache (replacing the inline ``python3 -c``
block in the ingest Snakefile).

The cache is a TSV with columns: ``level``, ``name``, ``query``, ``latitude``,
``longitude``.  ``query`` is the full geocoder query/context key; legacy caches
without a ``query`` column are accepted and migrated with ``query=name``.
On merge, existing ``(level, query)`` entries are kept (cache-first), new entries
are appended, and the result is written atomically to the workdir cache path.

Source: inline ``python3 -c`` heredoc in ``ingest/Snakefile`` (lines 227–235).
"""

import logging
from pathlib import Path
from typing import Union

import pandas as pd

logger = logging.getLogger(__name__)

_CACHE_COLS = ["level", "name", "query", "latitude", "longitude"]


def merge_coordinate_cache(
    new_latlongs: Union[str, Path],
    cache_path: Union[str, Path],
    output_path: Union[str, Path],
) -> None:
    """Merge newly geocoded coordinates into the persistent cache.

    Deduplicates on ``(level, query)`` keeping the cache entry (existing wins
    over new, preserving any manual coordinates in the seed).  Writes the
    result to *output_path* (which may be the same as *cache_path* for
    in-place update of the workdir cache).

    Args:
        new_latlongs: Path to the freshly generated ``latlongs.tsv``.
        cache_path: Path to the existing cache TSV (may not yet exist).
        output_path: Destination path for the updated cache TSV.
    """
    new_df = _read_cache(new_latlongs)
    if Path(cache_path).exists():
        old_df = _read_cache(cache_path)
        old_len = len(old_df)
        merged = pd.concat([old_df, new_df], ignore_index=True)
        merged = merged.drop_duplicates(subset=["level", "query"], keep="first")
        new_entries = max(len(merged) - old_len, 0)
    else:
        merged = new_df.drop_duplicates(subset=["level", "query"], keep="first")
        new_entries = len(merged)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out, sep="\t", index=False)
    logger.info(
        "Cache updated: %d entries → %s (%d new)",
        len(merged),
        out,
        new_entries,
    )


def _read_cache(path: Union[str, Path]) -> pd.DataFrame:
    """Read a coordinate cache TSV, returning an empty DataFrame if file is missing.

    Handles two on-disk formats transparently:
    - **New format** (written by ``merge_coordinate_cache``): has a header row
      starting with ``"level\\t"``.
    - **Legacy / latlongs format** (written by ``write_output`` or the old
      Snakefile inline block): no header; blank lines separate trait groups.
    """
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=_CACHE_COLS)

    with open(p, encoding="utf-8") as fh:
        first_line = fh.readline()

    if first_line.startswith("level\t"):
        df = pd.read_csv(p, sep="\t", dtype=str).fillna("")
        if "query" not in df.columns:
            df["query"] = df.get("name", "")
    else:
        df = pd.read_csv(
            p,
            sep="\t",
            header=None,
            names=_CACHE_COLS,
            dtype=str,
        ).fillna("")
        # Legacy files have four fields. Pandas fills the final column with
        # empty strings when five names are provided, so shift lat/lon back and
        # set query=name. Headerless v2 cache rows already have query filled.
        legacy_rows = df["longitude"].str.strip() == ""
        if legacy_rows.any():
            df.loc[legacy_rows, "longitude"] = df.loc[legacy_rows, "latitude"]
            df.loc[legacy_rows, "latitude"] = df.loc[legacy_rows, "query"]
            df.loc[legacy_rows, "query"] = df.loc[legacy_rows, "name"]
        # Drop blank-line rows (blank lines between trait groups in latlongs.tsv)
        df = df[df["name"].str.strip() != ""]

    for col in _CACHE_COLS:
        if col not in df.columns:
            df[col] = ""
    return df[_CACHE_COLS]
