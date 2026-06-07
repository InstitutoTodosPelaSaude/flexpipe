"""
ViralQC (BLAST + Nextclade) result join and cross-contamination filtering.

Left-joins ViralQC output (clade, genome_quality, coverage, virus, segment) into
the metadata DataFrame.  Sequences identified as the wrong virus or segment are
flagged genome_quality='D' so the downstream ``augur filter`` step removes them.

Extracted verbatim from ``scripts/curate.py`` (lines 235–308, the block at the
start of ``main()`` that begins ``if args.nextclade and os.path.isfile(…)``).
"""

import logging
import os
from pathlib import Path
from typing import Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)


def _normalized_viralqc_seq_name(value: str) -> str:
    """Return the metadata-compatible accession from a ViralQC sequence name."""
    return str(value).split("|", 1)[0].strip()


def _joinable_viralqc_table(nc: pd.DataFrame, nc_cols: dict) -> pd.DataFrame:
    """Return ViralQC rows keyed by exact and normalized sequence names."""
    nc_sub = nc[list(nc_cols)].rename(columns=nc_cols)
    nc_sub["strain"] = nc_sub["strain"].astype(str).str.strip()

    exact = nc_sub.copy()
    exact["_join_priority"] = 0

    normalized = nc_sub.copy()
    normalized["strain"] = normalized["strain"].map(_normalized_viralqc_seq_name)
    normalized["_join_priority"] = 1

    combined = pd.concat([exact, normalized], ignore_index=True)
    combined = combined[combined["strain"] != ""]
    combined = combined.sort_values("_join_priority").drop_duplicates("strain", keep="first")
    return combined.drop(columns=["_join_priority"])


def join_viralqc(
    df: pd.DataFrame,
    nextclade_path: Optional[Union[str, Path]],
    viralqc_cfg: dict,
) -> pd.DataFrame:
    """Merge ViralQC results into the metadata DataFrame.

    Performs a left-join on ``strain`` so every row in *df* is preserved.
    ViralQC columns added/updated:
    - ``clade``: overrides existing clade only when ViralQC assigned one
    - ``genome_quality``: A/B (pass), C/D (fail)
    - ``qc_overall_status``: from Nextclade ``qc.overallStatus``
    - ``coverage``: genome coverage fraction

    Virus/segment cross-contamination filtering:
    - If ``viralqc_cfg.expected_virus`` is set, sequences assigned a different
      (non-empty) virus are marked ``genome_quality='D'``
    - If ``viralqc_cfg.expected_segment`` is set, sequences with the wrong
      segment are marked ``genome_quality='D'``

    Args:
        df: Metadata DataFrame with at least a ``strain`` column.
        nextclade_path: Path to the ViralQC ``results.tsv`` output file (may be
            ``None`` or non-existent, in which case the join is skipped and
            placeholder columns are added).
        viralqc_cfg: The ``viralqc`` section of ``config.yaml`` as a dict.

    Returns:
        Updated DataFrame with ViralQC columns merged in.
    """
    clade_col = viralqc_cfg.get("clade_column", "clade")
    df = df.copy()
    if "qc_exclusion_reason" not in df.columns:
        df["qc_exclusion_reason"] = ""

    if nextclade_path and os.path.isfile(nextclade_path):
        nc = pd.read_csv(nextclade_path, sep="\t", dtype=str, keep_default_na=False).fillna("")
        if "seqName" not in nc.columns:
            raise SystemExit(
                f"Malformed ViralQC output: required column 'seqName' not found in {nextclade_path}"
            )

        nc_cols = {"seqName": "strain"}
        if clade_col in nc.columns:
            nc_cols[clade_col] = "_nc_clade"
        if "genomeQuality" in nc.columns:
            nc_cols["genomeQuality"] = "_nc_genome_quality"
        if "coverage" in nc.columns:
            nc_cols["coverage"] = "_nc_coverage"
        if "qc.overallStatus" in nc.columns:
            nc_cols["qc.overallStatus"] = "_nc_qc"
        if "virus" in nc.columns:
            nc_cols["virus"] = "_nc_virus"
        if "segment" in nc.columns:
            nc_cols["segment"] = "_nc_segment"

        nc_sub = _joinable_viralqc_table(nc, nc_cols)
        nc_sub["_has_viralqc"] = "1"
        df = df.merge(nc_sub, on="strain", how="left")

        missing_vqc = df["_has_viralqc"].fillna("") != "1"
        df.loc[missing_vqc, "qc_exclusion_reason"] = "missing_viralqc"
        df.drop(columns=["_has_viralqc"], inplace=True)

        if "_nc_clade" in df.columns:
            existing = df.get("clade", pd.Series("", index=df.index)).fillna("")
            has_nc_clade = df["_nc_clade"].notna() & (df["_nc_clade"].str.strip() != "")
            df["clade"] = df["_nc_clade"].where(has_nc_clade, existing)
            df.drop(columns=["_nc_clade"], inplace=True)

        if "_nc_genome_quality" in df.columns:
            df["genome_quality"] = df["_nc_genome_quality"].fillna("")
            poor_quality = df["genome_quality"].isin(["C", "D"]) & (
                df["qc_exclusion_reason"].str.strip() == ""
            )
            df.loc[poor_quality, "qc_exclusion_reason"] = "viralqc_quality"
            df.drop(columns=["_nc_genome_quality"], inplace=True)

        if "_nc_qc" in df.columns:
            df["qc_overall_status"] = df["_nc_qc"].fillna("")
            df.drop(columns=["_nc_qc"], inplace=True)

        if "_nc_coverage" in df.columns:
            df["coverage"] = pd.to_numeric(df["_nc_coverage"], errors="coerce")
            df.drop(columns=["_nc_coverage"], inplace=True)

        # Cross-contamination filter: sequences with wrong/unclassified virus
        expected_virus = viralqc_cfg.get("expected_virus", None)
        expected_segment = viralqc_cfg.get("expected_segment", None)

        if "_nc_virus" in df.columns:
            if expected_virus:
                virus_values = df["_nc_virus"].fillna("").astype(str).str.strip()
                present = virus_values != ""
                bad_virus = present & (virus_values != expected_virus)
                unclassified = present & virus_values.str.lower().str.contains(
                    "unclassified", na=False
                )
                exclude = bad_virus | unclassified
                n = int(exclude.sum())
                if n:
                    logger.warning(
                        "Excluding %d sequences with wrong/unclassified virus (expected: %s)",
                        n,
                        expected_virus,
                    )
                    if "genome_quality" not in df.columns:
                        df["genome_quality"] = ""
                    df.loc[exclude, "genome_quality"] = "D"
                    df.loc[exclude, "qc_exclusion_reason"] = "wrong_virus"
            df.drop(columns=["_nc_virus"], inplace=True)

        if "_nc_segment" in df.columns:
            if expected_segment:
                segment_values = df["_nc_segment"].fillna("").astype(str).str.strip()
                present = segment_values != ""
                bad_seg = present & (segment_values != expected_segment)
                n = int(bad_seg.sum())
                if n:
                    logger.warning(
                        "Excluding %d sequences with wrong segment (expected: %s)",
                        n,
                        expected_segment,
                    )
                    if "genome_quality" not in df.columns:
                        df["genome_quality"] = ""
                    df.loc[bad_seg, "genome_quality"] = "D"
                    # Preserve a more specific reason already set (e.g. wrong_virus);
                    # only write wrong_segment when the reason is still blank.
                    blank_reason = df["qc_exclusion_reason"].str.strip() == ""
                    df.loc[bad_seg & blank_reason, "qc_exclusion_reason"] = "wrong_segment"
            df.drop(columns=["_nc_segment"], inplace=True)
    else:
        df["qc_exclusion_reason"] = "missing_viralqc"

    # Ensure these columns always exist (even if ViralQC was not run)
    if "genome_quality" not in df.columns:
        df["genome_quality"] = ""
    if "qc_overall_status" not in df.columns:
        df["qc_overall_status"] = ""
    if "coverage" not in df.columns:
        df["coverage"] = float("nan")
    if "qc_exclusion_reason" not in df.columns:
        df["qc_exclusion_reason"] = ""

    return df
