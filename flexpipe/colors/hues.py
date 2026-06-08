"""
Deterministic hue assignment from subsampled metadata.

Assigns fixed hues to known top-level categories (continents, sources, etc.)
and spreads remaining hues evenly across unknown values using a hash-based
deterministic algorithm (same name → same hue across runs, regardless of
which other names exist in the dataset).

Hue wheel: 0–350, step 10.
  0=red  30=orange  70=yellow-green  90=green  140=teal  190=cyan
  200=blue  240=dark-blue  270=purple  290=violet  340=rose

Configuration:
  Clade truncation level is set in ``config.yaml → curation.clade_levels``
  (default 1 for YFV).  ``curate.py`` performs the truncation upstream;
  this script reads the ``clade_truncated`` column.

Hue tables are bundled in ``flexpipe/data/colors/*_hues.tsv`` and can be
overridden per-build via ``colours.hue_tables.*`` in config.

Extracted from ``scripts/generate_name2hue.py``.
Fixes applied:
- Module docstring updated (was referencing non-existent ``subsampling.lineage_levels``
  config key and the script ``curate_qc.py``; corrected to ``curation.clade_levels``
  and ``curate.py``).
- ``nearest_valid`` function removed (was defined but never called anywhere).
- ``LINEAGE_HUES`` renamed to ``CLADE_HUES`` (matches the ``clade_truncated`` column).
- ``print()`` replaced with ``logging``.
- Phase 3: hue tables loaded from ``flexpipe/data/colors/*_hues.tsv``.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
from pathlib import Path

import pandas as pd

from flexpipe.data import load_data_table

logger = logging.getLogger(__name__)


def load_hue_table(filename: str, override: str | None = None) -> dict:
    """Load a ``*_hues.tsv`` data file into a ``{category: hue_int}`` dict.

    Args:
        filename: Bundled file name (e.g. ``"region_hues.tsv"``).
        override: Optional path to a replacement file.  When provided and the
            file exists it is used instead of the bundled default.
    """
    df = load_data_table("flexpipe.data.colors", filename, override=override)
    return dict(zip(df["category"], df["hue"].astype(int)))


# ── geo (region = top-level of geo hierarchy) ────────────────────────────────
REGION_HUES = load_hue_table("region_hues.tsv")

# ── clade (clade_truncated = top-level of clade hierarchy) ────────────────────
# All clade_truncated values use deterministic hash-based hues automatically.
# Same name always → same hue across builds, regardless of how many clades exist.
# No manual curation needed as new clades emerge.
CLADE_HUES: dict = {}  # intentionally empty — hash fallback handles everything

# ── host ──────────────────────────────────────────────────────────────────────
HOST_HUES = load_hue_table("host_hues.tsv")

# ── source ────────────────────────────────────────────────────────────────────
SOURCE_HUES = load_hue_table("source_hues.tsv")

# ── data_use ──────────────────────────────────────────────────────────────────
DATA_USE_HUES = load_hue_table("data_use_hues.tsv")

# ── valid hue set (multiples of 10, 0-350) ────────────────────────────────────
VALID_HUES = set(range(0, 360, 10))


def stable_hash_hue(name: str, used_hues: set[int] | None = None) -> int:
    """Assign *name* to a deterministic hue bucket with collision probing."""
    used_hues = used_hues or set()
    digest = hashlib.sha256(str(name).encode("utf-8")).hexdigest()
    hue = (int(digest, 16) % 36) * 10
    for _ in range(36):
        if hue not in used_hues:
            return hue
        hue = (hue + 10) % 360
    return (int(digest, 16) % 36) * 10


def load_hue_cache(path: str | Path | None) -> dict[str, int]:
    """Load a persistent ``category TAB hue`` cache, ignoring malformed rows."""
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        df = pd.read_csv(p, sep="\t", dtype=str, comment="#").fillna("")
    except pd.errors.EmptyDataError:
        return {}
    if not {"category", "hue"}.issubset(df.columns):
        return {}
    result: dict[str, int] = {}
    for _, row in df.iterrows():
        category = str(row.get("category", "")).strip()
        hue_text = str(row.get("hue", "")).strip()
        if not category:
            continue
        try:
            hue = int(hue_text)
        except ValueError:
            continue
        if hue in VALID_HUES:
            result[category] = hue
    return result


def write_hue_cache(path: str | Path | None, cache: dict[str, int]) -> None:
    """Write the persistent hue cache."""
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as fh:
        fh.write("category\thue\n")
        for category, hue in sorted(cache.items(), key=lambda item: _natural_key(item[0])):
            fh.write(f"{category}\t{int(hue)}\n")


def _natural_key(s: str):
    """Sort key that handles mixed text/numbers: ``A.D.2 < A.D.10``."""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", s)]


def spread_hues(names: list) -> dict:
    """Spread N names evenly across the hue wheel (0–350, multiples of 10).

    Step = ``floor(360 / N)`` rounded down to the nearest 10, minimum 10.
    Names are sorted alphabetically + numerically so the spread is stable.

    Args:
        names: List of category names to assign hues to.

    Returns:
        ``{name: hue_int}`` dict.
    """
    n = len(names)
    if n == 0:
        return {}
    step = max(10, (360 // n // 10) * 10)
    ordered = sorted(names, key=_natural_key)
    return {name: (i * step) % 360 for i, name in enumerate(ordered)}


def collect(
    df: pd.DataFrame,
    col: str,
    fixed_hues: dict,
    label: str,
    use_hash_for_unknown: bool = False,
    cached_hues: dict[str, int] | None = None,
):
    """Return ``({value: hue}, warnings)`` for all non-empty values in ``df[col]``.

    Known values (in *fixed_hues*) get their fixed hue.  Unknown values either
    get a hash-spread hue (if *use_hash_for_unknown*) or the next available
    hue on the wheel.

    Args:
        df: Metadata DataFrame.
        col: Column to collect unique values from.
        fixed_hues: Mapping of known ``{value: hue}``.
        label: Human-readable label for log messages.
        use_hash_for_unknown: If ``True``, spread unknown values deterministically.

    Returns:
        Tuple ``(result_dict, warning_strings)``.
    """
    if col not in df.columns:
        logger.warning("Column '%s' not found — skipping %s", col, label)
        return {}, []

    values = sorted(
        set(v for v in df[col].tolist() if str(v).strip() not in ("", "nan", "NA", "NaN"))
    )

    result = {}
    warnings = []
    used = set(fixed_hues.values())
    cached_hues = cached_hues or {}

    known = [v for v in values if v in fixed_hues]
    unknown = [v for v in values if v not in fixed_hues]

    for v in known:
        result[v] = int(fixed_hues[v])

    if unknown:
        for v in unknown:
            used_result = set(result.values())
            cached = cached_hues.get(v)
            if cached in VALID_HUES:
                result[v] = int(cached)
                continue

            reserved = used | used_result
            if use_hash_for_unknown:
                h = stable_hash_hue(v, reserved)
            else:
                h = 0
                for _ in range(36):
                    if h not in reserved:
                        break
                    h = (h + 10) % 360
            result[v] = h
            warnings.append(
                f"{label}: '{v}' has no fixed hue → assigned {h}. "
                f"Add to flexpipe/data/colors/*_hues.tsv or set colours.hue_tables in config."
            )

    return result, warnings


def main() -> None:
    """Entry point for ``flexpipe-name2hue``."""
    parser = argparse.ArgumentParser(description="Generate name2hue.tsv from curated metadata")
    parser.add_argument("--metadata", required=True, help="Curated metadata TSV")
    parser.add_argument("--config", required=False, default=None)
    parser.add_argument("--output", required=True, help="Output name2hue.tsv")
    parser.add_argument(
        "--cache",
        required=False,
        default=None,
        help="Persistent category→hue cache to read/update",
    )
    args = parser.parse_args()

    from flexpipe.logging_setup import configure_logging

    configure_logging()

    logger.info("Loading metadata: %s", args.metadata)
    df = pd.read_csv(args.metadata, sep="\t", dtype=str).fillna("")

    # Start from bundled defaults; override if config specifies custom hue tables.
    region_hues = REGION_HUES
    host_hues = HOST_HUES
    source_hues = SOURCE_HUES
    data_use_hues = DATA_USE_HUES

    geo_root = "region"
    clade_root = "clade_truncated"

    if args.config:
        try:
            from flexpipe.config import load_config

            cfg = load_config(args.config, skip_viralqc=True)
            geo_root = cfg.colours.geo.split()[0]
            clade_root = cfg.colours.clade.split()[0]
            ht = cfg.colours.hue_tables
            if ht.region:
                region_hues = load_hue_table("region_hues.tsv", override=ht.region)
            if ht.host:
                host_hues = load_hue_table("host_hues.tsv", override=ht.host)
            if ht.source:
                source_hues = load_hue_table("source_hues.tsv", override=ht.source)
            if ht.data_use:
                data_use_hues = load_hue_table("data_use_hues.tsv", override=ht.data_use)
        except Exception as exc:
            logger.warning("Could not load hue-table overrides from config: %s", exc)

    all_warnings = []
    sections = []  # (comment, {cat: hue})
    persistent_cache = load_hue_cache(args.cache)

    def run(comment, col, fixed, label, use_hash=False):
        result, warns = collect(
            df,
            col,
            fixed,
            label,
            use_hash_for_unknown=use_hash,
            cached_hues=persistent_cache,
        )
        sections.append((comment, result))
        all_warnings.extend(warns)

    run(
        f"# geo (top-level = {geo_root})",
        geo_root,
        region_hues,
        geo_root,
        use_hash=True,
    )
    run(
        f"# clade (top-level = {clade_root}) — unknown = hash-based",
        clade_root,
        CLADE_HUES,
        clade_root,
        use_hash=True,
    )
    run("# host", "host", host_hues, "host")
    run("# source", "source", source_hues, "source")
    run("# data_use", "data_use", data_use_hues, "data_use")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    total = 0
    with open(args.output, "w") as fh:
        fh.write("category\thue\n")
        for comment, entries in sections:
            fh.write(f"\n{comment}\n")
            for cat, hue in sorted(entries.items()):
                fh.write(f"{cat}\t{hue}\n")
                total += 1
                persistent_cache[cat] = int(hue)

    logger.info("Wrote %d entries → %s", total, args.output)
    write_hue_cache(args.cache, persistent_cache)

    if all_warnings:
        logger.warning("Auto-assigned hues (add to *_hues.tsv to fix):")
        for w in all_warnings:
            logger.warning("  %s", w)
    else:
        logger.info("All categories matched fixed hue tables.")


if __name__ == "__main__":
    main()
