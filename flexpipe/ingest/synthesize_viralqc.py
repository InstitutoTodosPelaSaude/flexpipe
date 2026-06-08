"""Synthesize a minimal ViralQC results TSV for ``viralqc.mode='skip'``.

Used when QC should be bypassed (e.g. pre-curated local sequences that have
already been quality-controlled outside of flexpipe).  Every sequence gets
``genomeQuality='A'`` and ``qc.overallStatus='good'``, allowing the downstream
``augur filter`` step to retain all sequences.

**Important:** this mode bypasses contamination and coverage checks.  Use only
when the input sequences are already curated and quality-controlled.
``flexpipe-validate-build`` warns when ``viralqc.mode != 'run'``.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def iter_fasta_ids(fasta_path: str) -> list[str]:
    """Return a list of sequence IDs (header field before first space) from a FASTA file."""
    ids: list[str] = []
    with open(fasta_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped.startswith(">"):
                ids.append(stripped[1:].split()[0])
    return ids


def write_synthetic_viralqc_tsv(fasta_path: str, output_path: str) -> None:
    """Write a synthetic ViralQC results TSV for all sequences in *fasta_path*.

    Every sequence receives:

    - ``genomeQuality = 'A'`` (best quality grade)
    - ``coverage = '1.0'``
    - ``qc.overallStatus = 'good'``

    The join in ``flexpipe-curate`` then populates those columns as if ViralQC
    had run, allowing the pipeline to proceed to subsampling and phylogenetics
    without BLAST or Nextclade.

    Args:
        fasta_path: Path to the merged sequences FASTA produced by ``merge_local_sequences``.
        output_path: Destination path for the synthetic ``results.tsv``.
    """
    seq_ids = iter_fasta_ids(fasta_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["seqName", "genomeQuality", "coverage", "qc.overallStatus"])
        for seq_id in seq_ids:
            writer.writerow([seq_id, "A", "1.0", "good"])
    logger.info("synthesize_viralqc: wrote %d synthetic rows to %s", len(seq_ids), output_path)
