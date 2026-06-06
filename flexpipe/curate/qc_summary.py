"""
Per-run QC summary artifact — aggregates curation and filter statistics.

Produces two artifacts from a single run of the ingest pipeline:

* ``qc_report.json`` — structured JSON with total counts, per-grade breakdown,
  coverage statistics, cross-contamination flags, and augur-filter exclusion reasons.
* ``qc_summary.tsv`` — flat TSV with one row per genome-quality grade for quick
  inspection in a spreadsheet or ``grep``.

The report draws from three sources produced by the ``curate_qc`` Snakemake rule:

1. ``curated_metadata.tsv`` — all sequences before ``augur filter`` (has ``genome_quality``,
   ``coverage``, ``qc_overall_status``).
2. ``filter_log.tsv`` — per-strain exclusion log written by ``augur filter --output-log``
   (columns: ``strain``, ``filter``, ``kwargs``).
3. ``final_metadata.tsv`` — retained sequences after ``augur filter``.

Usage::

    flexpipe-qc-summary \\
        --curated     <workdir>/results/ingest/curated_metadata.tsv \\
        --filter-log  <workdir>/results/ingest/filter_log.tsv \\
        --final       <workdir>/results/ingest/final_metadata.tsv \\
        --qc-report   <workdir>/results/qc_report.json \\
        --qc-summary  <workdir>/results/qc_summary.tsv
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Union

import pandas as pd

from flexpipe.io import load_table

logger = logging.getLogger(__name__)


def build_qc_report(
    curated_path: Union[str, Path],
    filter_log_path: Union[str, Path],
    final_path: Union[str, Path],
) -> dict:
    """Build a structured QC report dictionary from the three ingest artifacts.

    Args:
        curated_path: Path to ``curated_metadata.tsv`` (all sequences, pre-filter).
        filter_log_path: Path to ``filter_log.tsv`` written by ``augur filter --output-log``.
        final_path: Path to ``final_metadata.tsv`` (retained sequences, post-filter).

    Returns:
        Dictionary with keys: ``total_curated``, ``total_retained``, ``total_excluded``,
        ``genome_quality_counts``, ``coverage_stats``, ``cross_contamination_count``,
        ``exclusion_by_filter``, ``exclusion_details``.
    """
    curated_path = Path(curated_path)
    filter_log_path = Path(filter_log_path)
    final_path = Path(final_path)

    # ── Load inputs ──────────────────────────────────────────────────────────
    logger.info("Loading curated metadata from %s", curated_path)
    curated = load_table(curated_path, dtype="str", fillna="")

    logger.info("Loading filter log from %s", filter_log_path)
    if filter_log_path.exists() and filter_log_path.stat().st_size > 0:
        try:
            filter_log = load_table(filter_log_path, dtype="str", fillna="")
        except Exception as exc:
            # Header-only or empty file (all sequences passed the filter)
            logger.info("Filter log unreadable or empty (%s) — no exclusion reasons available", exc)
            filter_log = pd.DataFrame(columns=["strain", "filter", "kwargs"])
    else:
        logger.info(
            "Filter log not found or empty: %s — no exclusion reasons available", filter_log_path
        )
        filter_log = pd.DataFrame(columns=["strain", "filter", "kwargs"])

    logger.info("Loading final metadata from %s", final_path)
    final = load_table(final_path, dtype="str", fillna="")

    # ── Totals ───────────────────────────────────────────────────────────────
    total_curated = len(curated)
    total_retained = len(final)
    total_excluded = total_curated - total_retained

    # ── Genome quality grade distribution ────────────────────────────────────
    grade_order = ["A", "B", "C", "D", ""]
    if "genome_quality" in curated.columns:
        grade_counts = curated["genome_quality"].value_counts(dropna=False)
        # Normalise: treat NaN as empty string
        grade_counts.index = grade_counts.index.fillna("")
    else:
        logger.warning("'genome_quality' column not found in curated metadata")
        grade_counts = pd.Series(dtype=int)

    genome_quality_counts: dict[str, int] = {}
    for grade in grade_order:
        genome_quality_counts[grade if grade else "(empty)"] = int(grade_counts.get(grade, 0))
    # Include any unexpected grades not in the standard set
    for grade, count in grade_counts.items():
        key = grade if grade else "(empty)"
        if key not in genome_quality_counts:
            genome_quality_counts[key] = int(count)

    # ── Coverage statistics ───────────────────────────────────────────────────
    coverage_stats: dict[str, object] = {}
    if "coverage" in curated.columns:
        cov = pd.to_numeric(curated["coverage"], errors="coerce")
        coverage_stats = {
            "mean": round(float(cov.mean()), 4) if not cov.isna().all() else None,
            "median": round(float(cov.median()), 4) if not cov.isna().all() else None,
            "min": round(float(cov.min()), 4) if not cov.isna().all() else None,
            "max": round(float(cov.max()), 4) if not cov.isna().all() else None,
            "missing_count": int(cov.isna().sum()),
        }
    else:
        logger.warning("'coverage' column not found in curated metadata")

    # ── Cross-contamination count ───────────────────────────────────────────
    # Count only explicit wrong-virus/wrong-segment reasons. Other D-grade
    # sequences are ViralQC quality failures, not necessarily contamination.
    if "qc_exclusion_reason" in curated.columns:
        cross_contamination_count = int(
            curated["qc_exclusion_reason"].isin(["wrong_virus", "wrong_segment"]).sum()
        )
    else:
        cross_contamination_count = 0

    # ── Exclusion reason breakdown from augur filter log ────────────────────
    exclusion_by_filter: dict[str, int] = {}
    if not filter_log.empty and "filter" in filter_log.columns:
        for reason, group in filter_log.groupby("filter"):
            exclusion_by_filter[str(reason)] = len(group)

    # ── Build report ─────────────────────────────────────────────────────────
    report = {
        "total_curated": total_curated,
        "total_retained": total_retained,
        "total_excluded": total_excluded,
        "genome_quality_counts": genome_quality_counts,
        "coverage_stats": coverage_stats,
        "cross_contamination_count": cross_contamination_count,
        "exclusion_by_filter": exclusion_by_filter,
    }

    logger.info(
        "QC report: %d curated → %d retained, %d excluded",
        total_curated,
        total_retained,
        total_excluded,
    )
    return report


def write_qc_artifacts(
    report: dict,
    qc_report_path: Union[str, Path],
    qc_summary_path: Union[str, Path],
) -> None:
    """Write the QC report JSON and a flat per-grade TSV summary.

    Args:
        report: The dict returned by :func:`build_qc_report`.
        qc_report_path: Output path for ``qc_report.json``.
        qc_summary_path: Output path for ``qc_summary.tsv``.
    """
    qc_report_path = Path(qc_report_path)
    qc_summary_path = Path(qc_summary_path)

    qc_report_path.parent.mkdir(parents=True, exist_ok=True)
    qc_summary_path.parent.mkdir(parents=True, exist_ok=True)

    # JSON report
    qc_report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    logger.info("QC report written to %s", qc_report_path)

    # Flat TSV: one row per genome_quality grade
    rows = [
        {"genome_quality": grade, "count": count}
        for grade, count in report.get("genome_quality_counts", {}).items()
    ]
    summary_df = pd.DataFrame(rows, columns=["genome_quality", "count"])
    summary_df["total_curated"] = report.get("total_curated", 0)
    summary_df["total_retained"] = report.get("total_retained", 0)
    summary_df["total_excluded"] = report.get("total_excluded", 0)
    summary_df.to_csv(qc_summary_path, sep="\t", index=False)
    logger.info("QC summary written to %s", qc_summary_path)


def main() -> None:
    """Entry point for ``flexpipe-qc-summary``."""
    parser = argparse.ArgumentParser(
        description=(
            "Build a per-run QC summary artifact from ingest curation outputs.\n\n"
            "Produces qc_report.json (structured) and qc_summary.tsv (flat per-grade table)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--curated",
        required=True,
        help="Path to curated_metadata.tsv (all sequences before augur filter)",
    )
    parser.add_argument(
        "--filter-log",
        required=True,
        help="Path to filter_log.tsv written by augur filter --output-log",
    )
    parser.add_argument(
        "--final",
        required=True,
        help="Path to final_metadata.tsv (retained sequences after augur filter)",
    )
    parser.add_argument(
        "--qc-report",
        required=True,
        help="Output path for qc_report.json",
    )
    parser.add_argument(
        "--qc-summary",
        required=True,
        help="Output path for qc_summary.tsv",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    report = build_qc_report(
        curated_path=args.curated,
        filter_log_path=args.filter_log,
        final_path=args.final,
    )
    write_qc_artifacts(
        report=report,
        qc_report_path=args.qc_report,
        qc_summary_path=args.qc_summary,
    )
