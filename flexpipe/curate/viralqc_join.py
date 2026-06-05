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

    if nextclade_path and os.path.isfile(nextclade_path):
        nc = pd.read_csv(nextclade_path, sep="\t", dtype=str, keep_default_na=False).fillna("")
        if "seqName" in nc.columns:
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

            nc_sub = nc[list(nc_cols)].rename(columns=nc_cols)
            df = df.merge(nc_sub, on="strain", how="left")

            if "_nc_clade" in df.columns:
                existing = df.get("clade", pd.Series("", index=df.index)).fillna("")
                has_nc_clade = df["_nc_clade"].notna() & (df["_nc_clade"].str.strip() != "")
                df["clade"] = df["_nc_clade"].where(has_nc_clade, existing)
                df.drop(columns=["_nc_clade"], inplace=True)

            if "_nc_genome_quality" in df.columns:
                df["genome_quality"] = df["_nc_genome_quality"].fillna("")
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
                    present = df["_nc_virus"].str.strip() != ""
                    bad_virus = present & (df["_nc_virus"].str.strip() != expected_virus)
                    unclassified = present & df["_nc_virus"].str.lower().str.contains(
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
                df.drop(columns=["_nc_virus"], inplace=True)

            if "_nc_segment" in df.columns:
                if expected_segment:
                    present = df["_nc_segment"].str.strip() != ""
                    bad_seg = present & (df["_nc_segment"].str.strip() != expected_segment)
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
                df.drop(columns=["_nc_segment"], inplace=True)

    # Ensure these columns always exist (even if ViralQC was not run)
    if "genome_quality" not in df.columns:
        df["genome_quality"] = ""
    if "qc_overall_status" not in df.columns:
        df["qc_overall_status"] = ""
    if "coverage" not in df.columns:
        df["coverage"] = float("nan")

    return df
