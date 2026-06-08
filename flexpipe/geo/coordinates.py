"""
Nominatim geocoder with rate-limiting, 429 handling, and incremental cache writes.

Extracted from ``scripts/get_coordinates.py`` (all logic was under ``__main__``).

Key changes vs the original:
- All logic lifted out of ``__main__`` into importable functions.
- Stale ``user_agent="flexpipe_rsv_nextstrain_build"`` fixed to ``"flexpipe_nextstrain_build"``.
- ``force_coordinates`` overrides moved to config (``coordinates.force`` key).
- Trailing top-level ``print(...)`` at the end of the original file removed (it ran on import).
- ``print()`` replaced with ``logging``.
"""

import argparse
import logging
import os
import time
from collections import defaultdict
from typing import Optional

import numpy as np
import pandas as pd
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)

# Nominatim ToS: unique user_agent + max 1 req/sec
_USER_AGENT = "flexpipe_nextstrain_build"
RATE_LIMIT_SLEEP = 2.0  # seconds between requests (conservative)
RATE_LIMIT_429_WAIT = 90.0  # seconds to wait after a 429 before retrying

# Map column level → Nominatim featuretype so division queries return states,
# not municipalities with the same name (e.g. "Amazonas" in Amapá vs the state).
FEATURETYPE = {
    "division": "state",
    "location": "city",
}


def _valid_place(value) -> bool:
    text = str(value).strip()
    return text not in ("", "NA", "NAN", "nan", "unknown", "-")


def _make_geolocator(user_agent: str = _USER_AGENT, timeout: int = 10) -> Nominatim:
    """Create a Nominatim geolocator instance."""
    return Nominatim(user_agent=user_agent, timeout=timeout)


def find_coordinates(
    place: str,
    level: Optional[str],
    geolocator: Nominatim,
    retries: int = 6,
) -> tuple[str, str]:
    """Query Nominatim with rate-limiting and retries.

    Args:
        place: Full query string (e.g. ``"Serra, Espírito Santo"``).
        level: Column level (``"division"``, ``"location"``, etc.) used to
            select the Nominatim ``featuretype`` hint.
        geolocator: A ``Nominatim`` instance.
        retries: Number of attempts before giving up.

    Returns:
        ``(latitude_str, longitude_str)`` or ``("NA", "NA")`` on failure.
    """
    featuretype = FEATURETYPE.get(level or "")
    for attempt in range(retries):
        try:
            time.sleep(RATE_LIMIT_SLEEP)
            kwargs = {"language": "en"}
            if featuretype:
                kwargs["featuretype"] = featuretype
            location = geolocator.geocode(place, **kwargs)
            if location:
                return (str(location.latitude), str(location.longitude))
            return ("NA", "NA")
        except Exception as exc:
            is_429 = (
                "429" in str(exc) or "Too Many" in str(exc) or "RateLimited" in type(exc).__name__
            )
            wait = RATE_LIMIT_429_WAIT if is_429 else RATE_LIMIT_SLEEP * (2**attempt)
            logger.warning(
                'Attempt %d failed for "%s": %s. Retrying in %.1fs...',
                attempt + 1,
                place,
                exc,
                wait,
            )
            time.sleep(wait)
    return ("NA", "NA")


def _read_cache_rows(cache_path: str, columns: list[str]) -> list[dict[str, str]]:
    """Read legacy/v2 coordinate cache rows into normalized dictionaries."""
    if not cache_path or not os.path.exists(cache_path):
        return []

    from flexpipe.geo.cache import _read_cache

    df = _read_cache(cache_path)
    if columns:
        df = df[df["level"].isin(columns)]
    return df.to_dict("records")


def load_cache(cache_path: str, columns: list[str]) -> dict[str, dict[str, tuple[str, str]]]:
    """Load a coordinate cache TSV into a nested ``{trait: {place: (lat, lon)}}`` dict.

    Args:
        cache_path: Path to the cache TSV file.
        columns: List of column names (traits) that are of interest.

    Returns:
        Nested dict initialised with keys for each column in *columns*.
    """
    results: dict[str, dict] = {trait: {} for trait in columns}
    for row in _read_cache_rows(cache_path, columns):
        trait = row.get("level", "")
        place = row.get("name", "")
        if trait in results and place:
            results[trait][place] = (str(row.get("latitude", "")), str(row.get("longitude", "")))
    return results


def load_cache_by_query(
    cache_path: str, columns: list[str]
) -> dict[str, dict[str, tuple[str, str]]]:
    """Load a coordinate cache keyed by ``(level, query)`` for geocoder identity."""
    results: dict[str, dict] = {trait: {} for trait in columns}
    for row in _read_cache_rows(cache_path, columns):
        trait = row.get("level", "")
        query = row.get("query", "") or row.get("name", "")
        if trait in results and query:
            results[trait][query] = (
                str(row.get("latitude", "")),
                str(row.get("longitude", "")),
            )
    return results


def write_output(
    results: dict[str, dict],
    output_path: str,
    force_coordinates: Optional[dict[str, tuple[str, str]]] = None,
) -> None:
    """Write geocoded results to the latlongs TSV file.

    Args:
        results: ``{trait: {place: (lat, lon)}}``.
        output_path: Destination file path.
        force_coordinates: Optional ``{place_name: (lat, lon)}`` overrides
            (e.g. ``{"Washington DC": ("38.91", "-77.01")}``).
    """
    force_coordinates = force_coordinates or {}
    with open(output_path, "w") as fh:
        for trait, lines in results.items():
            for place, coord in lines.items():
                if place in force_coordinates:
                    lat, lon = force_coordinates[place]
                else:
                    lat, lon = coord
                fh.write(f"{trait}\t{place}\t{lat}\t{lon}\n")
            fh.write("\n")


def build_queries(df: pd.DataFrame, columns: list[str]):
    """Build the ordered list of ``(level, query_parts)`` tuples from metadata.

    Deduplicates while preserving order.

    Args:
        df: Metadata DataFrame.
        columns: Column names to geocode (``"division"``, ``"location"``, etc.).

    Returns:
        List of ``(level, [parts])`` tuples for Nominatim queries.
    """
    traits = [c for c in columns if c != "region"]
    if not traits:
        return []

    queries = []
    for address in zip(*[df[t].values.tolist() for t in traits]):
        for position, _ in enumerate(address):
            level = traits[position]
            query = list(address[: position + 1])
            queries.append((level, query))

    seen = set()
    unique_queries = []
    for q in queries:
        key = (q[0], tuple(q[1]))
        if key not in seen:
            seen.add(key)
            unique_queries.append(q)
    return unique_queries


def disambiguate_geographic_values(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Rewrite ambiguous geographic values using the shortest unique parent suffix.

    Augur ``latlongs.tsv`` is keyed by ``(level, displayed name)``. If the same city
    name appears under multiple parent contexts, one displayed name cannot safely map
    to two coordinates. This function changes only ambiguous values, producing names
    such as ``Springfield, Illinois``.
    """
    out = df.copy()
    traits = [c for c in columns if c != "region" and c in out.columns]

    for idx, level in enumerate(traits):
        parent_cols = traits[:idx]
        if not parent_cols:
            continue

        contexts_by_name: dict[str, set[tuple[str, ...]]] = defaultdict(set)
        for _, row in out.iterrows():
            name = str(row.get(level, "")).strip()
            if not _valid_place(name):
                continue
            parent = tuple(str(row.get(col, "")).strip() for col in parent_cols)
            contexts_by_name[name].add(parent)

        for name, contexts in contexts_by_name.items():
            if len(contexts) <= 1:
                continue

            suffix_by_context: dict[tuple[str, ...], str] = {}
            for suffix_len in range(1, len(parent_cols) + 1):
                candidates = {
                    context: ", ".join(part for part in context[-suffix_len:] if _valid_place(part))
                    for context in contexts
                }
                values = [value for value in candidates.values() if value]
                if len(values) == len(contexts) and len(set(values)) == len(values):
                    suffix_by_context = candidates
                    break

            if not suffix_by_context:
                suffix_by_context = {
                    context: ", ".join(part for part in context if _valid_place(part))
                    for context in contexts
                }

            mask = out[level].astype(str).str.strip() == name
            for row_idx in out[mask].index:
                context = tuple(str(out.at[row_idx, col]).strip() for col in parent_cols)
                suffix = suffix_by_context.get(context, "")
                if suffix:
                    out.at[row_idx, level] = f"{name}, {suffix}"

    return out


def _dedupe_query_parts(parts: list[str]) -> list[str]:
    deduped = []
    for name in parts:
        if name not in deduped:
            deduped.append(name)
    return deduped


def _append_cache_row(
    cache_path: str,
    level: str,
    name: str,
    query: str,
    coord: tuple[str, str],
) -> None:
    with open(cache_path, "a") as cf:
        cf.write(f"{level}\t{name}\t{query}\t{coord[0]}\t{coord[1]}\n")


def geocode_metadata(
    df: pd.DataFrame,
    columns: list[str],
    cache_path: Optional[str],
    output_path: str,
    workdir_cache_path: Optional[str] = None,
    user_agent: str = _USER_AGENT,
    force_coordinates: Optional[dict[str, tuple[str, str]]] = None,
) -> None:
    """Geocode all locations in *df* for the given *columns*.

    Results are:
    1. Written to *output_path* (latlongs.tsv) incrementally after each new find.
    2. Appended incrementally to *workdir_cache_path* so a crash loses nothing.

    Args:
        df: Metadata DataFrame.
        columns: List of column names to geocode.
        cache_path: Read-only seed cache (build's ``cache_coordinates.tsv``).
        output_path: Output latlongs TSV (generated config artifact in workdir).
        workdir_cache_path: Writable cache in the workdir (appended incrementally).
        user_agent: Nominatim user agent string.
        force_coordinates: Optional overrides for specific place names.
    """
    force_coordinates = force_coordinates or {}
    df = disambiguate_geographic_values(df, columns)
    geolocator = _make_geolocator(user_agent=user_agent)
    results = load_cache(cache_path or "", columns)
    cache_by_query = load_cache_by_query(cache_path or "", columns)
    unique_queries = build_queries(df, columns)
    not_found = []

    for level, place_parts in unique_queries:
        target = place_parts[-1]
        if target in ("", "NA", "NAN", "unknown", "-", None) or target is np.nan:
            continue
        deduped = _dedupe_query_parts(place_parts)
        query = ", ".join(deduped)
        if query in cache_by_query.get(level, {}):
            results.setdefault(level, {})[target] = cache_by_query[level][query]
            continue
        if target in results.get(level, {}):
            continue  # already cached

        item = (level, query)
        if item in not_found:
            continue

        coord = find_coordinates(query, level=level, geolocator=geolocator)

        if "NA" in coord:
            not_found.append(item)
            logger.warning("Coordinates not found for: %s, %s", level, query)
        else:
            logger.info("→ %s, %s. Coordinates = %s", level, target, ", ".join(coord))
            results[level][target] = coord
            cache_by_query.setdefault(level, {})[query] = coord
            # Write incrementally after each find so a crash doesn't lose data
            write_output(results, output_path, force_coordinates)
            # Append to workdir cache incrementally
            if workdir_cache_path:
                _append_cache_row(workdir_cache_path, level, target, query, coord)

    # Final write (covers the case where no new coords were found, only cached)
    logger.info("Coordinates found and saved in the output file:")
    write_output(results, output_path, force_coordinates)

    for level, lines in results.items():
        for place, coord in lines.items():
            lat, lon = force_coordinates.get(place, coord)
            logger.debug("  %s → %s: %s, %s", level, place, lat, lon)

    if not_found:
        logger.warning(
            "Some coordinates were not found. Typos or special characters may cause this. "
            "Please fix them, re-run, or add coordinates manually: %s",
            not_found,
        )


def load_force_file(path: str) -> dict[str, tuple[str, str]]:
    """Load a manual-override coordinates TSV (``place TAB lat TAB lon``).

    Args:
        path: Path to the TSV file.

    Returns:
        ``{place: (lat_str, lon_str)}`` dict, empty if the file does not exist.
    """
    result: dict[str, tuple[str, str]] = {}
    if not path or not os.path.exists(path):
        return result
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                result[parts[0]] = (parts[1], parts[2])
    logger.debug("Loaded %d force-coordinate overrides from %s", len(result), path)
    return result


def main() -> None:
    """Entry point for ``flexpipe-coordinates``."""
    parser = argparse.ArgumentParser(
        description="Generate lat/long file for locations listed in a metadata file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--metadata", required=True, help="Nextstrain metadata TSV")
    parser.add_argument("--columns", nargs="+", type=str, help="Columns that need coordinates")
    parser.add_argument(
        "--cache", required=False, default=None, help="Pre-processed coordinates TSV"
    )
    parser.add_argument("--output", required=True, help="Output TSV with geographic coordinates")
    parser.add_argument(
        "--workdir-cache",
        required=False,
        default=None,
        help="Writable workdir cache path (appended incrementally)",
    )
    parser.add_argument(
        "--force-file",
        required=False,
        default=None,
        help="TSV file with manual coordinate overrides (place TAB lat TAB lon)",
    )
    parser.add_argument(
        "--metadata-output",
        required=False,
        default=None,
        help="Optional output TSV with ambiguous geographic names disambiguated",
    )
    parser.add_argument(
        "--disambiguate-only",
        action="store_true",
        help="Write disambiguated metadata to --output and skip geocoding",
    )
    args = parser.parse_args()

    from flexpipe.logging_setup import configure_logging

    configure_logging()

    force_coordinates = load_force_file(args.force_file) if args.force_file else {}

    df = pd.read_csv(args.metadata, sep="\t", dtype=str).fillna("")
    df = disambiguate_geographic_values(df, args.columns or [])
    if args.disambiguate_only:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        df.to_csv(args.output, sep="\t", index=False)
        logger.info("Wrote disambiguated metadata: %s", args.output)
        return
    if args.metadata_output:
        os.makedirs(os.path.dirname(os.path.abspath(args.metadata_output)), exist_ok=True)
        df.to_csv(args.metadata_output, sep="\t", index=False)
    geocode_metadata(
        df=df,
        columns=args.columns or [],
        cache_path=args.cache,
        output_path=args.output,
        workdir_cache_path=args.workdir_cache,
        force_coordinates=force_coordinates,
    )
    logger.info("Coordinates file successfully created.")


def main_disambiguate() -> None:
    """Entry point for ``flexpipe-disambiguate-geo``."""
    parser = argparse.ArgumentParser(
        description="Rewrite ambiguous geographic values in a metadata TSV",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--metadata", required=True, help="Input metadata TSV")
    parser.add_argument("--columns", nargs="+", type=str, help="Columns to check")
    parser.add_argument("--output", required=True, help="Output metadata TSV")
    args = parser.parse_args()

    from flexpipe.logging_setup import configure_logging

    configure_logging()

    df = pd.read_csv(args.metadata, sep="\t", dtype=str).fillna("")
    out = disambiguate_geographic_values(df, args.columns or [])
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    out.to_csv(args.output, sep="\t", index=False)
    logger.info("Wrote disambiguated metadata: %s", args.output)


if __name__ == "__main__":
    main()
