"""
Curate pipeline orchestrator.

Thin coordinator that calls the sub-modules in order:
  join_viralqc → apply_harmonization + coverage_from_completeness
  → drop_columns → divide_compounds → region → clade_truncated
  → source → normalize_host → rename_labs → normalize_data_use → dedup

This is the entry-point function for the ``flexpipe-curate`` console script.

Extracted from ``scripts/curate.py`` ``main()`` (lines 209–495).
"""

import argparse
import logging
import os

import pandas as pd
import pydantic

from flexpipe.config import load_config
from flexpipe.curate.clades import truncate_clade
from flexpipe.curate.columns import apply_harmonization, drop_columns
from flexpipe.curate.hosts import build_rules, normalize_host
from flexpipe.curate.regions import (
    _parse_brazil_division,
    build_brazil_maps,
    build_region_map,
    lookup_brazil_region,
    lookup_region_country,
)
from flexpipe.curate.viralqc_join import join_viralqc

logger = logging.getLogger(__name__)

_ITPS_SOURCE = "ITpS"


def run_curate(
    config_path: str,
    metadata_path: str,
    nextclade_path: str,
    output_path: str,
) -> None:
    """Run the full curation pipeline.

    Reads raw metadata, joins ViralQC results, harmonizes columns, assigns
    region and clade_truncated, normalizes hosts, deduplicates (preferring
    local ITpS records), and writes the curated TSV.

    Config is loaded via the validated ``FlexpipeConfig`` pydantic model so
    that override keys (``regions.country_map``, ``curation.host_rules``,
    ``colours.hue_tables.*``) are fully honoured.

    Args:
        config_path: Path to ``config.yaml``.
        metadata_path: Path to the augur-curate-renamed metadata TSV.
        nextclade_path: Path to ViralQC ``results.tsv`` (may be ``None``).
        output_path: Destination path for the curated metadata TSV.
    """
    try:
        cfg = load_config(config_path, skip_viralqc=True)
    except pydantic.ValidationError as exc:
        raise SystemExit(f"Config validation failed:\n{exc}") from exc

    nc_cfg = cfg.viralqc.model_dump()
    _ds = cfg.data_source
    default_source = "NCBI" if _ds == "ncbi" else "Pathoplexus"

    clade_levels = cfg.curation.clade_levels
    clade_sep = cfg.curation.clade_separator
    region_source = cfg.region_source
    division_parser = cfg.regions.division_parser

    # Build lookup maps — use config override paths when provided
    region_map = build_region_map(override=cfg.regions.country_map)
    brazil_region_map, brazil_norm, brazil_abbrev = build_brazil_maps(
        division_map_override=cfg.regions.division_map,
        abbrev_override=cfg.regions.division_abbreviations,
    )
    host_rules = build_rules(override=cfg.curation.host_rules)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    df = pd.read_csv(metadata_path, sep="\t", dtype=str).fillna("")
    logger.info("Loaded: %d rows", len(df))

    # ── join ViralQC (BLAST + Nextclade) ─────────────────────────────────────
    df = join_viralqc(df, nextclade_path, nc_cfg)

    # ── harmonize duplicate columns (PPX field → standard name) ──────────────
    # coverage: fill PPX rows (NaN) from LAPIS completeness field
    if "completeness" in df.columns:
        completeness_num = pd.to_numeric(df["completeness"], errors="coerce")
        df["coverage"] = df["coverage"].where(df["coverage"].notna(), completeness_num)
        df.drop(columns=["completeness"], inplace=True)

    df = apply_harmonization(df)

    # ── drop redundant / always-empty columns ─────────────────────────────────
    df = drop_columns(df)

    # ── normalise compound division strings (conditional on division_parser) ──
    if region_source == "division" and "division" in df.columns and division_parser == "brazil":
        parsed = df["division"].apply(lambda d: _parse_brazil_division(d, abbrev=brazil_abbrev))
        df["division"] = parsed.apply(lambda x: x[0])
        # Enrich location from the city part of compound division strings
        if "location" in df.columns:
            city_from_div = parsed.apply(lambda x: x[1])
            empty_loc = df["location"].str.strip() == ""
            has_city = city_from_div.str.strip() != ""
            df.loc[empty_loc & has_city, "location"] = city_from_div[empty_loc & has_city]

    # ── region ────────────────────────────────────────────────────────────────
    if region_source == "division" and "division" in df.columns:
        df["region"] = df["division"].apply(
            lambda d: lookup_brazil_region(d, region_map=brazil_region_map, norm_map=brazil_norm)
        )
        missing = df[df["region"] == ""]["division"].unique()
        if len(missing):
            logger.warning("No Brazil region mapping for divisions: %s", list(missing))
    elif "country" in df.columns:
        df["region"] = df["country"].apply(
            lambda c: lookup_region_country(c, region_map=region_map)
        )
        missing = df[df["region"] == ""]["country"].unique()
        if len(missing):
            logger.warning("No region mapping for countries: %s", list(missing))

    # ── clade_truncated ───────────────────────────────────────────────────────
    if "clade" in df.columns:
        df["clade_truncated"] = df["clade"].apply(
            lambda x: truncate_clade(x, clade_levels, clade_sep) if str(x).strip() else ""
        )

    # ── source ────────────────────────────────────────────────────────────────
    if "source" not in df.columns:
        df["source"] = default_source
    else:
        df["source"] = df["source"].replace("", default_source)

    # ── normalise host using config-driven rules ───────────────────────────────
    if "host" in df.columns:
        df["host"] = df["host"].apply(lambda h: normalize_host(h, rules=host_rules))

    # ── rename lab columns to display-friendly names ─────────────────────────
    df.rename(
        columns={
            "orig_lab_name": "Originating Lab",
            "subm_lab_name": "Submitting Lab",
        },
        inplace=True,
    )

    # ── normalise data_use to uppercase (OPEN / RESTRICTED) ───────────────────
    if "data_use" in df.columns:
        df["data_use"] = df["data_use"].str.strip().str.upper()

    # ── dedup — prefer local ITpS records over remote sources ─────────────────
    before = len(df)
    if "source" in df.columns:
        df = (
            df.assign(_prio=df["source"].apply(lambda s: 0 if s == _ITPS_SOURCE else 1))
            .sort_values("_prio", kind="stable")
            .drop_duplicates("strain")
            .drop(columns=["_prio"])
        )
    else:
        df = df.drop_duplicates("strain")
    if len(df) < before:
        logger.info("Deduplication: %d → %d", before, len(df))

    df.to_csv(output_path, sep="\t", index=False)
    logger.info("Output: %d rows → %s", len(df), output_path)


def main() -> None:
    """Entry point for ``flexpipe-curate``."""
    parser = argparse.ArgumentParser(description="Nextclade join + region + clade_truncated")
    parser.add_argument("--config", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--nextclade", required=False, default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    from flexpipe.logging_setup import configure_logging

    configure_logging()

    run_curate(
        config_path=args.config,
        metadata_path=args.metadata,
        nextclade_path=args.nextclade,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
