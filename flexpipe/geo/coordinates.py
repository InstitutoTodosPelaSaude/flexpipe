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
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)

# Nominatim ToS: unique user_agent + max 1 req/sec
_USER_AGENT = "flexpipe_nextstrain_build"
RATE_LIMIT_SLEEP = 2.0     # seconds between requests (conservative)
RATE_LIMIT_429_WAIT = 90.0  # seconds to wait after a 429 before retrying

# Map column level → Nominatim featuretype so division queries return states,
# not municipalities with the same name (e.g. "Amazonas" in Amapá vs the state).
FEATURETYPE = {
    "division": "state",
    "location": "city",
}


def _make_geolocator(user_agent: str = _USER_AGENT, timeout: int = 10) -> Nominatim:
    """Create a Nominatim geolocator instance."""
    return Nominatim(user_agent=user_agent, timeout=timeout)


def find_coordinates(
    place: str,
    level: Optional[str],
    geolocator: Nominatim,
    retries: int = 6,
) -> Tuple[str, str]:
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
    featuretype = FEATURETYPE.get(level)
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
            is_429 = "429" in str(exc) or "Too Many" in str(exc) or "RateLimited" in type(exc).__name__
            wait = RATE_LIMIT_429_WAIT if is_429 else RATE_LIMIT_SLEEP * (2 ** attempt)
            logger.warning(
                'Attempt %d failed for "%s": %s. Retrying in %.1fs...',
                attempt + 1, place, exc, wait,
            )
            time.sleep(wait)
    return ("NA", "NA")


def load_cache(cache_path: str, columns: List[str]) -> Dict[str, Dict[str, Tuple[str, str]]]:
    """Load a coordinate cache TSV into a nested ``{trait: {place: (lat, lon)}}`` dict.

    Args:
        cache_path: Path to the cache TSV file.
        columns: List of column names (traits) that are of interest.

    Returns:
        Nested dict initialised with keys for each column in *columns*.
    """
    results: Dict[str, Dict] = {trait: {} for trait in columns}
    if cache_path and os.path.exists(cache_path):
        with open(cache_path) as fh:
            for line in fh:
                if not line.startswith("\n"):
                    try:
                        trait, place, lat, lon = line.strip().split("\t")
                        if trait in results:
                            results[trait][place] = (str(lat), str(lon))
                    except Exception:
                        pass
    return results


def write_output(
    results: Dict[str, Dict],
    output_path: str,
    force_coordinates: Optional[Dict[str, Tuple[str, str]]] = None,
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


def build_queries(df: pd.DataFrame, columns: List[str]):
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


def geocode_metadata(
    df: pd.DataFrame,
    columns: List[str],
    cache_path: Optional[str],
    output_path: str,
    workdir_cache_path: Optional[str] = None,
    user_agent: str = _USER_AGENT,
    force_coordinates: Optional[Dict[str, Tuple[str, str]]] = None,
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
    geolocator = _make_geolocator(user_agent=user_agent)
    results = load_cache(cache_path, columns)
    unique_queries = build_queries(df, columns)
    not_found = []

    for level, place_parts in unique_queries:
        target = place_parts[-1]
        if target in ("", "NA", "NAN", "unknown", "-", None) or target is np.nan:
            continue
        if target in results.get(level, {}):
            continue  # already cached

        # Deduplicate query parts
        deduped = []
        for name in place_parts:
            if name not in deduped:
                deduped.append(name)

        item = (level, ", ".join(deduped))
        if item in not_found:
            continue

        coord = find_coordinates(", ".join(deduped), level=level, geolocator=geolocator)

        if "NA" in coord:
            not_found.append(item)
            logger.warning("Coordinates not found for: %s, %s", level, ", ".join(deduped))
        else:
            logger.info("→ %s, %s. Coordinates = %s", level, target, ", ".join(coord))
            results[level][target] = coord
            # Write incrementally after each find so a crash doesn't lose data
            write_output(results, output_path, force_coordinates)
            # Append to workdir cache incrementally
            if workdir_cache_path:
                with open(workdir_cache_path, "a") as cf:
                    cf.write(f"{level}\t{target}\t{coord[0]}\t{coord[1]}\n")

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


def main() -> None:
    """Entry point for ``flexpipe-coordinates``."""
    parser = argparse.ArgumentParser(
        description="Generate lat/long file for locations listed in a metadata file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--metadata", required=True, help="Nextstrain metadata TSV")
    parser.add_argument("--columns", nargs="+", type=str, help="Columns that need coordinates")
    parser.add_argument("--cache", required=False, default=None, help="Pre-processed coordinates TSV")
    parser.add_argument("--output", required=True, help="Output TSV with geographic coordinates")
    parser.add_argument("--workdir-cache", required=False, default=None,
                        help="Writable workdir cache path (appended incrementally)")
    args = parser.parse_args()

    from flexpipe.logging_setup import configure_logging
    configure_logging()

    df = pd.read_csv(args.metadata, sep="\t", dtype=str).fillna("")
    geocode_metadata(
        df=df,
        columns=args.columns or [],
        cache_path=args.cache,
        output_path=args.output,
        workdir_cache_path=args.workdir_cache,
    )
    logger.info("Coordinates file successfully created.")


if __name__ == "__main__":
    main()
