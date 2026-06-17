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

from flexpipe.curate.viralqc_aliases import label_matches_entry, resolve_expected_entry

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
    *,
    mode: str = "whole-genome",
) -> pd.DataFrame:
    """Merge ViralQC results into the metadata DataFrame.

    Performs a left-join on ``strain`` so every row in *df* is preserved.
    ViralQC columns added/updated:
    - ``clade``: overrides existing clade only when ViralQC assigned one
    - ``genome_quality``: A/B (pass), C/D (fail)
    - ``qc_overall_status``: from Nextclade ``qc.overallStatus``
    - ``coverage``: genome coverage fraction

    When ``mode='fragment'``, three additional columns are joined from ViralQC's
    per-target metrics (present when ViralQC ran a gene/region dataset):
    - ``target_gene_coverage``: ``targetGeneCoverage`` as a float (0–1)
    - ``target_gene_quality``: ``targetGeneQuality`` grade (A/B/C/D)
    - ``target_gene``: ``targetGene`` name (e.g. ``"N"``)

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
        mode: Pipeline mode — ``"whole-genome"`` (default) or ``"fragment"``.
            Whole-genome output is byte-identical regardless of this flag.

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
        # Fragment mode: join per-target-gene coverage/quality columns when present
        if mode == "fragment":
            if "targetGeneCoverage" in nc.columns:
                nc_cols["targetGeneCoverage"] = "_nc_target_gene_coverage"
            if "targetGeneQuality" in nc.columns:
                nc_cols["targetGeneQuality"] = "_nc_target_gene_quality"
            if "targetGene" in nc.columns:
                nc_cols["targetGene"] = "_nc_target_gene"

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

        # Fragment mode: per-target-gene metrics
        if "_nc_target_gene_coverage" in df.columns:
            # targetGeneCoverage may be a plain float OR a "GENE: float" / "G1: v1, G2: v2"
            # dict-like string produced by ViralQC when multiple target genes exist.
            # Extract the numeric value for the primary target gene (the value of the
            # targetGene column for that row) or, as a fallback, the first numeric value found.
            tg_col = "_nc_target_gene" if "_nc_target_gene" in df.columns else None

            def _parse_coverage(row):
                val = row["_nc_target_gene_coverage"]
                if pd.isna(val) or str(val).strip() == "":
                    return float("nan")
                s = str(val).strip()
                # Plain float (e.g. "0.97")
                try:
                    return float(s)
                except ValueError:
                    pass
                # "GENE: float" or "G1: v1, G2: v2, ..." dict-like format
                gene = str(row[tg_col]).strip() if tg_col and tg_col in row.index else ""
                first_key = None
                first_val = float("nan")
                for part in s.split(","):
                    part = part.strip()
                    if ":" not in part:
                        continue
                    k, v = part.split(":", 1)
                    try:
                        num = float(v.strip())
                    except ValueError:
                        continue
                    if gene and k.strip() == gene:
                        return num  # exact match for configured target gene
                    if pd.isna(first_val):
                        first_key = k.strip()
                        first_val = num  # keep first numeric value as fallback
                if not pd.isna(first_val) and gene and first_key and first_key != gene:
                    logger.warning(
                        "targetGeneCoverage gene-name skew for '%s': "
                        "expected '%s' but not found in dict '%s'; "
                        "using first-entry value from gene '%s'.",
                        row.get("strain", "?"),
                        gene,
                        s,
                        first_key,
                    )
                return first_val

            df["target_gene_coverage"] = df.apply(_parse_coverage, axis=1)
            df.drop(columns=["_nc_target_gene_coverage"], inplace=True)
        if "_nc_target_gene_quality" in df.columns:
            df["target_gene_quality"] = df["_nc_target_gene_quality"].fillna("")
            df.drop(columns=["_nc_target_gene_quality"], inplace=True)
        if "_nc_target_gene" in df.columns:
            df["target_gene"] = df["_nc_target_gene"].fillna("")
            df.drop(columns=["_nc_target_gene"], inplace=True)

        # Cross-contamination filter: sequences with wrong/unclassified virus
        expected_virus = viralqc_cfg.get("expected_virus", None)
        expected_segment = viralqc_cfg.get("expected_segment", None)
        aliases_file = viralqc_cfg.get("aliases_file", None)

        if "_nc_virus" in df.columns:
            if expected_virus:
                virus_entry = resolve_expected_entry(
                    expected_virus,
                    "viruses",
                    aliases_file=aliases_file,
                )
                assert virus_entry is not None
                virus_values = df["_nc_virus"].fillna("").astype(str).str.strip()
                present = virus_values != ""
                bad_virus = present & ~virus_values.map(
                    lambda label: label_matches_entry(label, virus_entry)
                )
                unclassified = present & virus_values.str.lower().str.contains(
                    "unclassified", na=False
                )
                exclude = bad_virus | unclassified
                n = int(exclude.sum())
                if n:
                    logger.warning(
                        "Excluding %d sequences with wrong/unclassified virus "
                        "(expected: %s; alias key: %s)",
                        n,
                        expected_virus,
                        virus_entry.key if virus_entry else expected_virus,
                    )
                    if "genome_quality" not in df.columns:
                        df["genome_quality"] = ""
                    df.loc[exclude, "genome_quality"] = "D"
                    df.loc[exclude, "qc_exclusion_reason"] = "wrong_virus"
            df.drop(columns=["_nc_virus"], inplace=True)

        if "_nc_segment" in df.columns:
            if expected_segment:
                segment_entry = resolve_expected_entry(
                    expected_segment,
                    "segments",
                    aliases_file=aliases_file,
                )
                assert segment_entry is not None
                segment_values = df["_nc_segment"].fillna("").astype(str).str.strip()
                present = segment_values != ""
                bad_seg = present & ~segment_values.map(
                    lambda label: label_matches_entry(label, segment_entry)
                )
                n = int(bad_seg.sum())
                if n:
                    logger.warning(
                        "Excluding %d sequences with wrong segment "
                        "(expected: %s; alias key: %s)",
                        n,
                        expected_segment,
                        segment_entry.key if segment_entry else expected_segment,
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

    # Fragment mode: ensure target columns always exist so downstream rules can
    # reference them unconditionally (even when ViralQC did not produce them).
    if mode == "fragment":
        if "target_gene_coverage" not in df.columns:
            df["target_gene_coverage"] = float("nan")
        if "target_gene_quality" not in df.columns:
            df["target_gene_quality"] = ""
        if "target_gene" not in df.columns:
            df["target_gene"] = ""

    return df
