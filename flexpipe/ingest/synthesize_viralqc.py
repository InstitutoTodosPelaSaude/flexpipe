"""Synthesize a minimal ViralQC results TSV for ``viralqc.mode='skip'``.

Used when QC should be bypassed (e.g. pre-curated local sequences that have
already been quality-controlled outside of flexpipe, or a virus with no ViralQC
Nextclade dataset).  Every sequence gets ``genomeQuality='A'`` and
``qc.overallStatus='good'``, allowing the downstream ``augur filter`` step to
retain all sequences.

When ``genome_size > 0`` is supplied, ``coverage`` is computed as
``min(sequence_length / genome_size, 1.0)`` so that ``qc.min_coverage`` acts as
a real length-based filter.  When ``genome_size == 0`` (default), every sequence
gets ``coverage = '1.0'`` (backward-compatible behaviour).

**Important:** this mode bypasses contamination and segment checks.  Use only
when the input sequences are already curated and quality-controlled, or when the
target virus is absent from the ViralQC BLAST reference set (no dataset virus).
``flexpipe-validate-build`` warns when ``viralqc.mode != 'run'``.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _iter_fasta_ids_and_seqlens(fasta_path: str) -> list[tuple[str, int]]:
    """Return a list of (id, sequence_length) pairs from a FASTA file.

    Sequence length is measured in FASTA bases (excluding header and blank
    lines); gap characters and IUPAC ambiguity codes are counted as-is.
    """
    result: list[tuple[str, int]] = []
    current_id: str | None = None
    current_len: int = 0
    with open(fasta_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped.startswith(">"):
                if current_id is not None:
                    result.append((current_id, current_len))
                current_id = stripped[1:].split()[0]
                current_len = 0
            elif current_id is not None:
                current_len += len(stripped)
    if current_id is not None:
        result.append((current_id, current_len))
    return result


def iter_fasta_ids(fasta_path: str) -> list[str]:
    """Return a list of sequence IDs (header field before first space) from a FASTA file."""
    return [seq_id for seq_id, _ in _iter_fasta_ids_and_seqlens(fasta_path)]


def write_synthetic_viralqc_tsv(
    fasta_path: str,
    output_path: str,
    genome_size: int = 0,
) -> None:
    """Write a synthetic ViralQC results TSV for all sequences in *fasta_path*.

    Every sequence receives:

    - ``genomeQuality = 'A'`` (best quality grade)
    - ``qc.overallStatus = 'good'``
    - ``coverage``:
        - When *genome_size* > 0: ``min(seq_len / genome_size, 1.0)`` (4 d.p.)
        - When *genome_size* == 0 (default): ``'1.0'`` (unchanged behaviour)

    The join in ``flexpipe-curate`` then populates those columns as if ViralQC
    had run, allowing the pipeline to proceed to subsampling and phylogenetics
    without BLAST or Nextclade.

    When *genome_size* > 0, ``qc.min_coverage`` in the build config acts as a
    real minimum-length gate: sequences shorter than
    ``genome_size * min_coverage`` bp are assigned a fractional coverage and
    excluded by the downstream ``augur filter`` step.

    Args:
        fasta_path: Path to the merged sequences FASTA produced by ``merge_local_sequences``.
        output_path: Destination path for the synthetic ``results.tsv``.
        genome_size: Expected genome size in bp.  0 means no length-based
            coverage (every sequence gets coverage 1.0).
    """
    ids_and_lengths = _iter_fasta_ids_and_seqlens(fasta_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["seqName", "genomeQuality", "coverage", "qc.overallStatus"])
        for seq_id, seq_len in ids_and_lengths:
            if genome_size > 0:
                cov = str(round(min(seq_len / genome_size, 1.0), 4))
            else:
                cov = "1.0"
            writer.writerow([seq_id, "A", cov, "good"])
    logger.info(
        "synthesize_viralqc: wrote %d synthetic rows to %s (genome_size=%d)",
        len(ids_and_lengths),
        output_path,
        genome_size,
    )
