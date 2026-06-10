"""
Clade/lineage group filter — keep or drop sequences by a metadata-column value.

Sits between the ``curate_qc`` rule and ``prepare`` (augur subsample) in the
ingest workflow.  The filter is intentionally column-agnostic: it can operate
on ``clade``, ``clade_truncated``, ``genotype``, ``major_lineage``,
``minor_lineage``, or any other curated column.

Behaviour when disabled (the default for builds that omit a ``clade_filter``
section, or set ``clade_filter.column: ""``):

* The full curated + QC-filtered metadata and sequences are passed through
  unchanged.  A header-only log is written.

Behaviour when the configured column is absent from the metadata at runtime:

* A loud warning is emitted and the filter is skipped (pass-through).  This
  is intentional: ``clade`` and ``clade_truncated`` are only present when
  ViralQC / the upstream pipeline supplies a clade assignment, so a hard
  error would break builds where the column legitimately doesn't exist.

Usage::

    flexpipe-filter-clade \\
        --config    builds/measles-b3-global/config.yaml \\
        --metadata  <workdir>/results/ingest/final_metadata.tsv \\
        --sequences <workdir>/results/ingest/final_sequences.fasta \\
        --output-metadata  <workdir>/results/ingest/clade_filtered_metadata.tsv \\
        --output-sequences <workdir>/results/ingest/clade_filtered_sequences.fasta \\
        --log              <workdir>/results/ingest/clade_filter_log.tsv
"""

import argparse
import logging
from pathlib import Path

import pandas as pd
import yaml

from flexpipe.io import load_table, read_fasta_records, write_fasta

logger = logging.getLogger(__name__)


def _matches(value: str, target: str, match: str) -> bool:
    """Return True if *value* matches *target* under the given *match* mode.

    ``"exact"``  — ``value == target``
    ``"prefix"`` — ``value == target`` *or* ``value.startswith(target + ".")``.
                   The dot-boundary prevents ``B3`` from matching ``B30``.
    """
    if match == "prefix":
        return value == target or value.startswith(target + ".")
    # default: exact
    return value == target


def filter_by_clade(
    metadata_df: pd.DataFrame,
    column: str,
    include: list[str],
    exclude: list[str],
    match: str = "exact",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply include/exclude filtering on a metadata column.

    Args:
        metadata_df: Input metadata DataFrame (values as strings).
        column:      Name of the column to filter on.  Empty string disables
                     the filter and returns *metadata_df* unchanged.
        include:     If non-empty, keep only rows whose column value matches
                     one of these targets.  Rows not matching are dropped with
                     ``drop_reason="not_in_include"``.
        exclude:     Drop rows whose column value matches one of these targets.
                     Applied after *include*.  Dropped rows carry
                     ``drop_reason="in_exclude"``.
        match:       ``"exact"`` (default) or ``"prefix"`` (dot-boundary).

    Returns:
        ``(kept_df, dropped_df)`` where *dropped_df* has two extra columns:
        ``group_value`` (the observed column value) and ``drop_reason``
        (``"not_in_include"`` or ``"in_exclude"``).
        When the filter is disabled or the column is missing, returns
        ``(metadata_df, empty_dropped_df)``.
    """
    _empty_dropped = pd.DataFrame(columns=["strain", "group_value", "drop_reason"])

    # ── Disabled ──────────────────────────────────────────────────────────────
    if not column:
        logger.info(
            "clade_filter disabled (column not set) — passing through %d rows", len(metadata_df)
        )
        return metadata_df.copy(), _empty_dropped

    # ── Missing column ─────────────────────────────────────────────────────────
    if column not in metadata_df.columns:
        logger.warning(
            "clade_filter column %r not present in metadata; "
            "passing through %d rows without filtering. "
            "Check that curation produces this column (clade/clade_truncated require a "
            "ViralQC clade assignment; genotype/major_lineage/minor_lineage require "
            "curation.lineage_parser != 'none').",
            column,
            len(metadata_df),
        )
        return metadata_df.copy(), _empty_dropped

    # ── Apply include ──────────────────────────────────────────────────────────
    df = metadata_df.copy()
    dropped_rows: list[pd.DataFrame] = []

    if include:
        include_set = include  # keep as list for prefix-match iteration
        mask_keep = df[column].apply(
            lambda v: any(_matches(str(v).strip(), t, match) for t in include_set)
        )
        not_in = df[~mask_keep].copy()
        if not not_in.empty:
            not_in["group_value"] = not_in[column]
            not_in["drop_reason"] = "not_in_include"
            dropped_rows.append(not_in[["strain", "group_value", "drop_reason"]])
        df = df[mask_keep].reset_index(drop=True)

    # ── Apply exclude ──────────────────────────────────────────────────────────
    if exclude:
        exclude_set = exclude
        mask_drop = df[column].apply(
            lambda v: any(_matches(str(v).strip(), t, match) for t in exclude_set)
        )
        in_excl = df[mask_drop].copy()
        if not in_excl.empty:
            in_excl["group_value"] = in_excl[column]
            in_excl["drop_reason"] = "in_exclude"
            dropped_rows.append(in_excl[["strain", "group_value", "drop_reason"]])
        df = df[~mask_drop].reset_index(drop=True)

    dropped_df = (
        pd.concat(dropped_rows, ignore_index=True)
        if dropped_rows
        else pd.DataFrame(columns=["strain", "group_value", "drop_reason"])
    )

    logger.info(
        "[clade_filter] %d kept, %d dropped (column=%r, include=%r, exclude=%r, match=%r)",
        len(df),
        len(dropped_df),
        column,
        include,
        exclude,
        match,
    )
    return df, dropped_df


def main() -> None:
    """Entry point for ``flexpipe-filter-clade``."""
    parser = argparse.ArgumentParser(
        description=(
            "Keep or drop sequences by a metadata-column value, upstream of subsampling.\n\n"
            "Reads the clade_filter section from the build config.yaml.  When that section\n"
            "is absent or column is empty, all sequences are passed through unchanged."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the build config.yaml (reads clade_filter section).",
    )
    parser.add_argument(
        "--metadata",
        required=True,
        help="Path to input metadata TSV (curated + QC-filtered).",
    )
    parser.add_argument(
        "--sequences",
        required=True,
        help="Path to input sequences FASTA.",
    )
    parser.add_argument(
        "--output-metadata",
        required=True,
        dest="output_metadata",
        help="Path to write filtered metadata TSV.",
    )
    parser.add_argument(
        "--output-sequences",
        required=True,
        dest="output_sequences",
        help="Path to write filtered sequences FASTA.",
    )
    parser.add_argument(
        "--log",
        required=True,
        help="Path to write per-strain drop log TSV (header-only when nothing dropped).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # ── Read clade_filter config (raw YAML — keep the CLI light) ──────────────
    config_path = Path(args.config)
    try:
        raw_cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.error("Could not read config %s: %s", config_path, exc)
        raise SystemExit(1) from exc

    cf = raw_cfg.get("clade_filter", {}) or {}
    column: str = str(cf.get("column", "") or "").strip()
    include: list[str] = [str(v).strip() for v in cf.get("include", []) if str(v).strip()]
    exclude: list[str] = [str(v).strip() for v in cf.get("exclude", []) if str(v).strip()]
    match: str = str(cf.get("match", "exact") or "exact").strip()

    # ── Load metadata ─────────────────────────────────────────────────────────
    metadata_df = load_table(args.metadata, dtype="str", fillna="")

    # ── Filter ────────────────────────────────────────────────────────────────
    kept, dropped = filter_by_clade(metadata_df, column, include, exclude, match)

    # ── Write metadata ────────────────────────────────────────────────────────
    out_meta = Path(args.output_metadata)
    out_meta.parent.mkdir(parents=True, exist_ok=True)
    kept.to_csv(out_meta, sep="\t", index=False)
    logger.info("Wrote %d metadata rows to %s", len(kept), out_meta)

    # ── Write sequences ───────────────────────────────────────────────────────
    kept_ids: set[str] = (
        set(kept["strain"].str.split().str[0]) if "strain" in kept.columns else set()
    )
    records = read_fasta_records(args.sequences)
    subset = [r for r in records if r.id.split()[0] in kept_ids]
    # Log any metadata/FASTA mismatches without erroring
    fasta_ids = {r.id.split()[0] for r in records}
    meta_only = kept_ids - fasta_ids
    fasta_only = fasta_ids - kept_ids
    if meta_only:
        logger.warning(
            "%d strains in kept metadata have no FASTA record (will be absent from output): %s",
            len(meta_only),
            sorted(meta_only)[:5],
        )
    if fasta_only:
        logger.warning(
            "%d FASTA records have no metadata entry and will be dropped: %s",
            len(fasta_only),
            sorted(fasta_only)[:5],
        )
    write_fasta(subset, args.output_sequences)
    logger.info("Wrote %d sequences to %s", len(subset), args.output_sequences)

    # ── Write drop log ────────────────────────────────────────────────────────
    out_log = Path(args.log)
    out_log.parent.mkdir(parents=True, exist_ok=True)
    dropped[["strain", "group_value", "drop_reason"]].to_csv(out_log, sep="\t", index=False)
    logger.info("Wrote clade_filter_log to %s (%d rows dropped)", out_log, len(dropped))
