"""Extract a gene or coordinate window from a whole-genome reference.gb.

Produces a gene-only GenBank record suitable for use as ``files.reference``
in a fragment-mode flexpipe build, plus an optional gene-relative terminal
mask BED file.

Usage::

    flexpipe-reference-slice \\
        --reference  builds/measles-b3-global/reference.gb \\
        --region     1233..1682 \\
        --gene       N  --feature-type CDS \\
        --new-id     NC_001498.1 \\
        --output-reference  builds/measles-b3-n450-global/reference.gb \\
        --output-bed        builds/measles-b3-n450-global/masks/reference_terminal.bed

The ``--region`` flag accepts 1-based inclusive coordinates in the source
reference (e.g. ``1233..1682`` for the measles N450 window).  When
``--region`` is not given, the slice is derived by looking up the first
feature of ``--feature-type`` (default ``CDS``) whose ``/gene`` qualifier
matches ``--gene``.

The output GenBank record is written in gene-relative coordinates (position 1
in the output = ``start`` in the source).  All GenBank features whose
intervals overlap the window are rewritten into the new coordinate frame by
Biopython's ``record[start:end]`` slicing.  A single CDS spanning the full
slice is synthesised when no CDS survives the slice (e.g. for a bare
``--region`` with no matching feature).

The optional ``--output-bed`` writes a gene-relative terminal mask BED using
the same ``derive_terminal_masks`` machinery as ``flexpipe-reference-mask``.
For a tight coding-sequence window (no UTR flanks) the BED will be empty,
which is correct and harmless.
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

from Bio import SeqIO
from Bio.SeqFeature import FeatureLocation, SeqFeature

from flexpipe.phylo.reference_mask import (
    _feature_intervals,
    derive_terminal_masks,
    load_mask_profile,
    write_bed,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _parse_region(region_str: str) -> tuple[int, int]:
    """Parse a 1-based inclusive region string (``START..END``) into a
    0-based half-open ``(start, end)`` tuple.

    >>> _parse_region("1233..1682")
    (1232, 1682)
    """
    m = re.fullmatch(r"(\d+)\.\.(\d+)", region_str.strip())
    if not m:
        raise ValueError(
            f"Invalid --region '{region_str}'. Expected 1-based 'START..END', e.g. '1233..1682'."
        )
    start_1based = int(m.group(1))
    end_1based = int(m.group(2))
    if start_1based < 1:
        raise ValueError(f"--region start must be >= 1, got {start_1based}")
    if end_1based < start_1based:
        raise ValueError(f"--region end ({end_1based}) must be >= start ({start_1based})")
    return start_1based - 1, end_1based  # 0-based half-open


def _find_feature_interval(
    record,
    gene_name: str,
    feature_type: str,
) -> tuple[int, int, int]:
    """Return the 0-based half-open ``(start, end, strand)`` spanning all intervals
    of the named gene feature.

    ``strand`` is 1 (forward) or -1 (reverse); falls back to 1 if the feature
    has no strand information.  Raises ``ValueError`` if no matching feature is found.
    """
    matching_features = []
    candidates = []
    for feature in record.features:
        if str(feature.type) != feature_type:
            continue
        gene_vals = [str(v) for v in feature.qualifiers.get("gene", [])]
        if gene_name not in gene_vals:
            continue
        matching_features.append(feature)
        candidates.extend(_feature_intervals(feature))
    if not candidates:
        raise ValueError(
            f"No {feature_type!r} feature with /gene='{gene_name}' found in "
            f"{record.id!r}.\n"
            "Check --gene and --feature-type, or use --region to specify "
            "coordinates explicitly."
        )
    first_start = min(s for s, _e in candidates)
    last_end = max(e for _s, e in candidates)

    # Determine strand from the first matching feature; warn when inconsistent.
    strand = int(matching_features[0].location.strand or 1)
    strands = {int(f.location.strand or 1) for f in matching_features}
    if len(strands) > 1:
        logger.warning(
            "Feature '%s'/%s has inconsistent strands across parts; "
            "using strand=%d for the synthesised features.",
            gene_name,
            feature_type,
            strand,
        )

    has_compound = any(len(_feature_intervals(f)) > 1 for f in matching_features)
    if has_compound:
        logger.warning(
            "Feature '%s'/%s has a compound/join location (%d parts). "
            "The slice will span %d..%d (the outer bounding interval). "
            "Review the output reference before use.",
            gene_name,
            feature_type,
            len(candidates),
            first_start + 1,
            last_end,
        )
    return first_start, last_end, strand


def _ensure_source_feature(sub_record, organism: str, strand: int = 1) -> None:
    """Ensure a ``source`` feature spanning the full record exists.

    Biopython's slice operator only carries over features whose coordinates
    lie entirely *within* the slice window.  Features that completely span the
    window (e.g. a whole-genome ``source`` annotation) are silently dropped.
    ``augur translate`` requires a ``source`` feature, so we synthesise one
    when none is present.

    Args:
        sub_record: The sliced BioPython SeqRecord to modify in-place.
        organism: Organism name for the ``/organism`` qualifier.
        strand: Strand of the original feature (1 or -1); used for the
            synthesised ``source`` feature.
    """
    has_source = any(str(f.type) == "source" for f in sub_record.features)
    if has_source:
        return
    length = len(sub_record.seq)
    source_f = SeqFeature(
        location=FeatureLocation(0, length, strand=strand),
        type="source",
        qualifiers={"organism": [organism]} if organism else {},
    )
    sub_record.features.insert(0, source_f)


def _ensure_cds_feature(sub_record, gene_name: str, strand: int = 1) -> None:
    """Ensure at least one CDS feature with /gene=gene_name exists.

    ``augur translate`` needs a CDS in the reference to produce amino-acid
    mutations.  If Biopython's slicing left no CDS (e.g. the user specified
    a bare ``--region`` outside any annotated CDS), synthesise one spanning
    the full record.

    Args:
        sub_record: The sliced BioPython SeqRecord to modify in-place.
        gene_name: Value for the ``/gene`` and ``/product`` qualifiers.
        strand: Strand of the original feature (1 or -1).  Negative-strand
            genes are rare in single-gene fragment builds, but passing the
            correct strand ensures ``augur translate`` reads the right frame.
    """
    has_cds = any(str(f.type) == "CDS" for f in sub_record.features)
    if has_cds:
        return
    length = len(sub_record.seq)
    if length % 3 != 0:
        logger.warning(
            "Synthesised CDS 1..%d /gene='%s': length %d is not a multiple of 3. "
            "Ensure --region starts on a codon boundary; otherwise augur translate "
            "will produce incorrect amino-acid mutations.",
            length,
            gene_name,
            length,
        )
    logger.warning(
        "No CDS feature in the sliced record — synthesising CDS 1..%d /gene='%s' "
        "strand=%d.  Review the output reference.",
        length,
        gene_name,
        strand,
    )
    cds = SeqFeature(
        location=FeatureLocation(0, length, strand=strand),
        type="CDS",
        qualifiers={"gene": [gene_name], "product": [gene_name]},
    )
    sub_record.features.append(cds)


def slice_reference(
    source: str | Path,
    *,
    region: str | None = None,
    gene: str | None = None,
    feature_type: str = "CDS",
    new_id: str | None = None,
) -> object:  # Bio.SeqRecord.SeqRecord
    """Slice a GenBank record to a gene/region window.

    Args:
        source: Path to the source whole-genome GenBank file.
        region: ``"START..END"`` in 1-based inclusive coordinates.  If given,
            ``gene`` / ``feature_type`` are used only to ensure/synthesise a
            CDS feature in the output.
        gene: ``/gene`` qualifier to match when ``region`` is omitted.
        feature_type: Feature type to search (default ``"CDS"``).
        new_id: Record ID for the output; defaults to the source ID.

    Returns:
        A ``Bio.SeqRecord.SeqRecord`` in gene-relative coordinates.
    """
    record = SeqIO.read(str(source), "genbank")
    effective_gene = gene or ""
    # Strand is resolved from the matched feature when --gene is used; for bare
    # --region slices the strand is unknown and defaults to 1 (forward).
    strand: int = 1

    if region:
        start, end = _parse_region(region)
        logger.info(
            "Slicing %s:%d..%d (0-based half-open) from %s",
            record.id,
            start,
            end,
            source,
        )
    elif effective_gene:
        start, end, strand = _find_feature_interval(record, effective_gene, feature_type)
        logger.info(
            "Found %s/%s at %d..%d (strand=%d); slicing",
            effective_gene,
            feature_type,
            start,
            end,
            strand,
        )
    else:
        raise ValueError("Provide --region or --gene to specify the slice.")

    if end > len(record.seq):
        raise ValueError(
            f"Slice end {end} exceeds reference length {len(record.seq)}. "
            "Check --region coordinates."
        )

    sub = record[start:end]
    sub.id = new_id if new_id else record.id
    sub.name = sub.id
    sub.description = (
        f"{record.description} [{start + 1}..{end}]"
        if region
        else f"{record.description} [{effective_gene} gene]"
    )

    # Ensure molecule_type annotation (required for GenBank output)
    mol_type = record.annotations.get("molecule_type", "RNA")
    sub.annotations.setdefault("molecule_type", mol_type)
    sub.annotations.setdefault("organism", record.annotations.get("organism", ""))

    # Ensure source and CDS features exist for augur translate.
    # Biopython drops features that completely span the slice (both endpoints
    # outside the window), so a whole-genome `source` annotation is never
    # carried over automatically — we synthesise it here using the original
    # feature's strand so negative-strand genes translate correctly.
    organism = record.annotations.get("organism", "")
    _ensure_source_feature(sub, organism, strand=strand)
    _ensure_cds_feature(sub, effective_gene or "target", strand=strand)

    logger.info(
        "Sliced record %s: %d bp, %d features",
        sub.id,
        len(sub.seq),
        len(sub.features),
    )
    return sub


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for ``flexpipe-reference-slice``."""
    parser = argparse.ArgumentParser(
        description=(
            "Slice a gene or coordinate window from a whole-genome reference.gb, "
            "producing a gene-only reference and optional gene-relative mask BED."
        )
    )
    parser.add_argument("--reference", required=True, help="Whole-genome source GenBank file.")
    parser.add_argument(
        "--region",
        default="",
        help=(
            "1-based inclusive coordinates 'START..END' in the source reference "
            "(e.g. '1233..1682' for measles N450). Overrides --gene."
        ),
    )
    parser.add_argument(
        "--gene",
        default="",
        help="Name of the /gene qualifier to locate the slice (e.g. 'N' for nucleoprotein).",
    )
    parser.add_argument(
        "--feature-type",
        default="CDS",
        help="Feature type to search when using --gene (default: 'CDS').",
    )
    parser.add_argument(
        "--new-id",
        default="",
        help="Record ID to assign to the output (default: keep source ID).",
    )
    parser.add_argument(
        "--output-reference",
        required=True,
        help="Path to write the gene-only GenBank output.",
    )
    parser.add_argument(
        "--output-bed",
        default="",
        help="Optional: path to write a gene-relative terminal mask BED.",
    )
    parser.add_argument(
        "--profile",
        default="default",
        help="Mask profile name from reference_mask_profiles.yaml (used with --output-bed).",
    )
    parser.add_argument(
        "--profile-file",
        default="",
        help="Override path for the mask profiles YAML (used with --output-bed).",
    )
    args = parser.parse_args()

    from flexpipe.logging_setup import configure_logging

    configure_logging()

    sub = slice_reference(
        args.reference,
        region=args.region or None,
        gene=args.gene or None,
        feature_type=args.feature_type,
        new_id=args.new_id or None,
    )

    out_path = Path(args.output_reference)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    SeqIO.write(sub, str(out_path), "genbank")
    logger.info("Wrote gene-only reference to %s", out_path)

    if args.output_bed:
        profile = load_mask_profile(args.profile_file or None, profile=args.profile)
        intervals = derive_terminal_masks(sub, profile)
        write_bed(sub.id, intervals, args.output_bed)
        logger.info(
            "Wrote %d gene-relative mask intervals to %s",
            len(intervals),
            args.output_bed,
        )


if __name__ == "__main__":
    main()
