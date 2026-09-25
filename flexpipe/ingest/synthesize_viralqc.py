"""Synthesize a minimal ViralQC results TSV for ``viralqc.mode='skip'``.

Used when QC should be bypassed (e.g. pre-curated local sequences that have
already been quality-controlled outside of flexpipe, or a virus with no ViralQC
Nextclade dataset).  Every sequence gets ``genomeQuality='A'`` and
``qc.overallStatus='good'``, allowing the downstream ``augur filter`` step to
retain all sequences.

When ``genome_size > 0`` is supplied, ``coverage`` is computed as
``min(unambiguous_bases / genome_size, 1.0)``, where unambiguous bases are
A, C, G, T and U.  Ambiguity codes, N and gaps do not count, so
``qc.min_coverage`` gates on how much of the genome was actually resolved.
When ``genome_size == 0`` (default), every sequence gets ``coverage = '1.0'``
(backward-compatible behaviour).

Note that ``viralqc.mode='run'`` reports real coverage from ViralQC, so the two
modes now mean the same thing by ``coverage``.

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


_UNAMBIGUOUS = frozenset("ACGTUacgtu")


def _iter_fasta_base_counts(fasta_path: str) -> list[tuple[str, int, int]]:
    """Return (id, total_length, unambiguous_bases) triples from a FASTA file.

    Total length counts every character on the sequence lines, including gaps,
    N and IUPAC ambiguity codes.  The unambiguous count keeps only A, C, G, T
    and U, which is what coverage is measured against.
    """
    result: list[tuple[str, int, int]] = []
    current_id: str | None = None
    current_len: int = 0
    current_unambiguous: int = 0
    with open(fasta_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped.startswith(">"):
                if current_id is not None:
                    result.append((current_id, current_len, current_unambiguous))
                current_id = stripped[1:].split()[0]
                current_len = 0
                current_unambiguous = 0
            elif current_id is not None:
                current_len += len(stripped)
                current_unambiguous += sum(1 for ch in stripped if ch in _UNAMBIGUOUS)
    if current_id is not None:
        result.append((current_id, current_len, current_unambiguous))
    return result


def iter_fasta_ids(fasta_path: str) -> list[str]:
    """Return a list of sequence IDs (header field before first space) from a FASTA file."""
    return [seq_id for seq_id, _, _ in _iter_fasta_base_counts(fasta_path)]


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
        - When *genome_size* > 0: ``min(unambiguous_bases / genome_size, 1.0)``
          (4 d.p.); A, C, G, T and U count, N and ambiguity codes do not
        - When *genome_size* == 0 (default): ``'1.0'`` (unchanged behaviour)

    The join in ``flexpipe-curate`` then populates those columns as if ViralQC
    had run, allowing the pipeline to proceed to subsampling and phylogenetics
    without BLAST or Nextclade.

    When *genome_size* > 0, ``qc.min_coverage`` in the build config acts as a
    real resolved-genome gate: a sequence resolving fewer than
    ``genome_size * min_coverage`` unambiguous bases is assigned a fractional
    coverage and excluded by the downstream ``augur filter`` step.

    Args:
        fasta_path: Path to the merged sequences FASTA produced by ``merge_local_sequences``.
        output_path: Destination path for the synthetic ``results.tsv``.
        genome_size: Expected genome size in bp.  0 means no coverage
            computation (every sequence gets coverage 1.0).
    """
    base_counts = _iter_fasta_base_counts(fasta_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["seqName", "genomeQuality", "coverage", "qc.overallStatus"])
        for seq_id, _seq_len, n_unambiguous in base_counts:
            if genome_size > 0:
                cov = str(round(min(n_unambiguous / genome_size, 1.0), 4))
            else:
                cov = "1.0"
            writer.writerow([seq_id, "A", cov, "good"])
    logger.info(
        "synthesize_viralqc: wrote %d synthetic rows to %s (genome_size=%d)",
        len(base_counts),
        output_path,
        genome_size,
    )
