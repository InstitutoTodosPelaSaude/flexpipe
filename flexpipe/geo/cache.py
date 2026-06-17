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

from flexpipe.data import load_data_table

logger = logging.getLogger(__name__)

_CACHE_COLS = ["level", "name", "query", "latitude", "longitude"]


def _empty_cache_df() -> pd.DataFrame:
    return pd.DataFrame(columns=_CACHE_COLS)


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


def validate_coordinate_cache(path: Union[str, Path]) -> pd.DataFrame:
    """Read and validate a coordinate cache TSV in normalized v2 form."""
    p = Path(path)
    with p.open(encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
    missing = [col for col in _CACHE_COLS if col not in header]
    if missing:
        raise ValueError(f"Coordinate cache missing columns: {missing}")
    df = pd.read_csv(p, sep="\t", dtype=str).fillna("")
    missing = [col for col in _CACHE_COLS if col not in df.columns]
    if missing:
        raise ValueError(f"Coordinate cache missing columns: {missing}")
    bad = df[(df["level"].str.strip() == "") | (df["name"].str.strip() == "")]
    if len(bad):
        raise ValueError(f"Coordinate cache has {len(bad)} rows with blank level/name")
    return df


def _read_shared_cache(override: Union[str, Path, None]) -> pd.DataFrame:
    if override:
        return validate_coordinate_cache(override)
    return load_data_table(
        "flexpipe.data.geo",
        "cache_coordinates.tsv",
        comment="#",
    ).fillna(
        ""
    )[_CACHE_COLS]


def seed_coordinate_cache(
    *,
    shared_cache: Union[str, Path, None],
    build_cache: Union[str, Path, None],
    output_path: Union[str, Path],
) -> None:
    """Seed the workdir coordinate cache from shared and build-specific sources.

    Shared entries are loaded first; build-specific entries are loaded second and
    win on duplicate ``(level, query)`` keys. Runtime geocoding still writes only
    to the workdir cache.
    """
    shared_df = _read_shared_cache(shared_cache)
    build_df = (
        _read_cache(build_cache)
        if build_cache and Path(build_cache).exists()
        else pd.DataFrame(columns=_CACHE_COLS)
    )
    merged = pd.concat([shared_df, build_df], ignore_index=True)
    if len(merged):
        merged = merged.drop_duplicates(subset=["level", "query"], keep="last")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out, sep="\t", index=False)
    logger.info(
        "Seeded coordinate cache with %d shared + %d build entries → %s",
        len(shared_df),
        len(build_df),
        out,
    )


def _read_cache(path: Union[str, Path]) -> pd.DataFrame:
    """Read a coordinate cache TSV, returning an empty DataFrame if file is missing.

    Handles two on-disk formats transparently:
    - **New format**: ``level name query latitude longitude``.
    - **Legacy headered format**: ``level name latitude longitude`` or
      ``level query lat lon display_name``.
    - **Legacy / latlongs format**: no header; blank lines separate trait groups.
    """
    p = Path(path)
    if not p.exists():
        return _empty_cache_df()
    if p.stat().st_size == 0:
        return _empty_cache_df()

    with open(p, encoding="utf-8") as fh:
        first_line = fh.readline()

    first_fields = first_line.rstrip("\n").split("\t")
    if first_fields and first_fields[0] == "level":
        df = pd.read_csv(p, sep="\t", dtype=str).fillna("")
        if "lat" in df.columns and "latitude" not in df.columns:
            df["latitude"] = df["lat"]
        if "lon" in df.columns and "longitude" not in df.columns:
            df["longitude"] = df["lon"]
        if "name" not in df.columns:
            if "display_name" in df.columns:
                display = df["display_name"].astype(str).str.strip()
                query = df.get("query", pd.Series([""] * len(df), index=df.index))
                df["name"] = display.where(display != "", query)
            else:
                df["name"] = df.get("query", "")
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
    df = df[df["name"].astype(str).str.strip() != ""]
    return df[_CACHE_COLS]
