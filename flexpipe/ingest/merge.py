"""
Merge remote (Pathoplexus / NCBI) data with local ITpS surveillance sequences.

Remote data source can be either Pathoplexus or NCBI; both output PPX-style
column names so the merge logic is identical.

Local focal data can be in two ITpS formats (auto-detected):
  - ``xlsx``  (ITpS old format — header detected by ``original_seq_id`` row)
  - ``tsv``   (ITpS new format — detected by ``ID`` column, PascalCase headers)

Both ITpS formats are mapped to PPX column names so that ``curate`` can
handle Pathoplexus/NCBI and ITpS data uniformly.

The FASTA file is always the authority: only sequences present in the FASTA
are included from the local metadata.

Extracted from ``scripts/merge_local_sequences.py``.
``print()`` calls replaced with ``logging``.
Minor docstring fix: was "Merge NCBI sequences…" — NCBI is only one possible source.
"""

import argparse
import logging
import os
import sys

import pandas as pd
from Bio import SeqIO

from flexpipe.data import load_data_yaml
from flexpipe.io import read_fasta_ids  # avoids duplicating the same helper


def _load_viralqc_cols() -> set[str]:
    data = load_data_yaml("flexpipe.data.curation", "viralqc_itps_columns.yaml")
    return set(data.get("viralqc_columns", []))


_VQC_COLS: set[str] = _load_viralqc_cols()

logger = logging.getLogger(__name__)


# ── ITpS xlsx field → Pathoplexus PPX column name ────────────────────────────
XLSX_TO_PPX = {
    "original_seq_id": "accessionVersion",
    "collection_date": "sampleCollectionDate",
    "country": "geoLocCountry",
    "state": "geoLocAdmin1",
    "city": "geoLocAdmin2",
    "host_species": "hostNameCommon",
    "data_use": "dataUseTerms",
    "authors": "authors",
    "age": "hostAge",
    "sex": "hostGender",
    "specimen_id": "specimenCollectorSampleId",
    "seq_instrument": "sequencingInstrument",
    "seq_tech": "sequencingProtocol",
    "depth_of_coverage": "depthOfCoverage",
    "sample_type": "sampleType",
}

# ── ITpS new TSV format (PascalCase headers, 'ID' as identifier) → PPX ───────
ITPS_TSV_TO_PPX = {
    "ID": "accessionVersion",
    "CollectionDate": "sampleCollectionDate",
    "Country": "geoLocCountry",
    "State": "geoLocAdmin1",
    "City": "geoLocAdmin2",
    "HostSpecies": "hostNameCommon",
    "DataUse": "dataUseTerms",
    "Authors": "authors",
    "HostAge": "hostAge",
    "HostSex": "hostGender",
    "OriginalSampleID": "specimenCollectorSampleId",
    "SequenceInstrument": "sequencingInstrument",
    "SequenceTechnology": "sequencingProtocol",
    "DepthOfCoverage": "depthOfCoverage",
    "SampleType": "sampleType",
    "AuthorAffiliations": "affiliations",
    "OriginalLaboratoryName": "orig_lab_name",
    "OriginalLaboratoryAddress": "orig_lab_address",
    "SubmissionLaboratoryName": "subm_lab_name",
    "SubmissionLaboratoryAddress": "subm_lab_address",
    "HostHealthState": "health_state",
    "HostHealthOutcome": "health_outcome",
    "HostSignsAndSymptoms": "signs_and_symptoms",
    "HostDisease": "host_disease",
    "HostTravelHistory": "travel_history",
    "PathogenSpecies": "pathogen_common_name",
    "OriginalHostSpecimenID": "sample_code",
}


def read_fasta_records(path: str) -> dict:
    """Return ``{seq_id: sequence_str}`` from a FASTA file."""
    records = {}
    for rec in SeqIO.parse(path, "fasta"):
        sid = rec.id.split()[0]
        if sid not in records:
            records[sid] = str(rec.seq)
    return records


def read_xlsx_metadata(path: str) -> pd.DataFrame:
    """Read ITpS xlsx, auto-detect header row, map columns to PPX names.

    The header is identified by finding the row that contains
    ``'original_seq_id'``.
    """
    raw = pd.read_excel(path, header=None, dtype=str).fillna("")

    header_row = None
    for i, row in raw.iterrows():
        if "original_seq_id" in row.values:
            header_row = i
            break

    if header_row is None:
        logger.error("'original_seq_id' column not found in xlsx: %s", path)
        sys.exit(1)

    df = pd.read_excel(path, header=header_row, dtype=str).fillna("")
    df = df[df["original_seq_id"].str.strip() != ""].reset_index(drop=True)
    df = df.rename(columns={k: v for k, v in XLSX_TO_PPX.items() if k in df.columns})
    df["source"] = "ITpS"
    if "dataUseTerms" in df.columns:
        df["dataUseTerms"] = df["dataUseTerms"].str.strip().str.upper()
    return df


def read_itps_tsv_metadata(path: str) -> pd.DataFrame:
    """Read ITpS new TSV format (PascalCase columns, ``'ID'`` as identifier)."""
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False).fillna("")
    df = df.rename(columns={k: v for k, v in ITPS_TSV_TO_PPX.items() if k in df.columns})
    df["source"] = "ITpS"
    if "dataUseTerms" in df.columns:
        df["dataUseTerms"] = df["dataUseTerms"].str.strip().str.upper()
    # Drop ViralQC output columns (they'll be re-added by curate after the pipeline run)
    df.drop(columns=[c for c in _VQC_COLS if c in df.columns], inplace=True)
    return df


def read_local_metadata(path: str) -> pd.DataFrame:
    """Auto-detect and read local ITpS metadata in any supported format.

    Supported formats:
    - ``.xlsx`` / ``.xls``: ITpS old format (``original_seq_id`` header detection)
    - ``.tsv`` with ``ID`` column: ITpS new PascalCase TSV
    - ``.tsv`` with ``accessionVersion`` or PPX headers: pass-through
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return read_xlsx_metadata(path)
    df_peek = pd.read_csv(path, sep="\t", dtype=str, nrows=0, keep_default_na=False)
    if (
        "ID" in df_peek.columns
        and "original_seq_id" not in df_peek.columns
        and "accessionVersion" not in df_peek.columns
        and "strain" not in df_peek.columns
    ):
        return read_itps_tsv_metadata(path)
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False).fillna("")
    if "dataUseTerms" in df.columns:
        df["dataUseTerms"] = df["dataUseTerms"].str.strip().str.upper()
    return df


def detect_id_column(df: pd.DataFrame) -> str:
    """Return the ID column name (``accessionVersion`` or ``strain``)."""
    for col in ("accessionVersion", "strain"):
        if col in df.columns:
            return col
    raise ValueError(f"No ID column (accessionVersion/strain) found. Got: {list(df.columns)}")


def main() -> None:
    """Entry point for ``flexpipe-merge``."""
    parser = argparse.ArgumentParser(description="Merge Pathoplexus and local sequences/metadata")
    parser.add_argument("--pathoplexus-metadata", required=True)
    parser.add_argument("--pathoplexus-sequences", required=True)
    parser.add_argument("--local-metadata", required=False, default="")
    parser.add_argument("--local-sequences", required=False, default="")
    parser.add_argument("--enabled", required=False, default="false")
    parser.add_argument("--metadata-output", required=True)
    parser.add_argument("--sequences-output", required=True)
    args = parser.parse_args()

    from flexpipe.logging_setup import configure_logging

    configure_logging()

    local_enabled = str(args.enabled).lower() in ("true", "1", "yes")

    os.makedirs(os.path.dirname(args.metadata_output), exist_ok=True)
    os.makedirs(os.path.dirname(args.sequences_output), exist_ok=True)

    # Load remote (Pathoplexus or NCBI) data
    logger.info("Loading remote metadata: %s", args.pathoplexus_metadata)
    ppx_meta = pd.read_csv(args.pathoplexus_metadata, sep="\t", dtype=str).fillna("")
    ppx_id_col = detect_id_column(ppx_meta)

    logger.info("Loading remote sequences: %s", args.pathoplexus_sequences)
    ppx_seqs = read_fasta_records(args.pathoplexus_sequences)
    logger.info("  %d metadata rows, %d sequences", len(ppx_meta), len(ppx_seqs))

    merged_meta = ppx_meta.copy()
    merged_seqs = dict(ppx_seqs)

    # Optionally merge local sequences
    if local_enabled and args.local_metadata and args.local_sequences:
        if not os.path.isfile(args.local_metadata):
            logger.warning("Local metadata not found: %s", args.local_metadata)
        elif not os.path.isfile(args.local_sequences):
            logger.warning("Local sequences not found: %s", args.local_sequences)
        else:
            logger.info("Loading local sequences: %s", args.local_sequences)
            fasta_ids = read_fasta_ids(args.local_sequences)
            local_seqs = read_fasta_records(args.local_sequences)
            logger.info("  %d sequences in FASTA", len(fasta_ids))

            logger.info("Loading local metadata: %s", args.local_metadata)
            local_meta = read_local_metadata(args.local_metadata)
            local_id_col = detect_id_column(local_meta)

            before = len(local_meta)
            local_meta = local_meta[local_meta[local_id_col].isin(fasta_ids)].reset_index(drop=True)
            logger.info("  %d metadata rows → %d matched to FASTA", before, len(local_meta))

            missing = fasta_ids - set(local_meta[local_id_col])
            if missing:
                logger.warning(
                    "%d FASTA IDs have no metadata entry: %s",
                    len(missing),
                    sorted(missing),
                )

            if local_id_col != ppx_id_col:
                local_meta[ppx_id_col] = local_meta[local_id_col]

            existing_ids = set(ppx_meta[ppx_id_col])
            new_local_meta = local_meta[~local_meta[ppx_id_col].isin(existing_ids)].copy()
            new_local_seqs = {k: v for k, v in local_seqs.items() if k not in existing_ids}
            logger.info("  Adding %d new local records", len(new_local_meta))

            merged_meta = pd.concat([ppx_meta, new_local_meta], ignore_index=True).fillna("")
            merged_seqs.update(new_local_seqs)
    else:
        if local_enabled:
            logger.info("local_sequences.enabled=true but paths not provided; skipping local merge")
        else:
            logger.info("local_sequences.enabled=false; using only remote data")

    merged_meta.to_csv(args.metadata_output, sep="\t", index=False)
    logger.info("Merged metadata: %d rows → %s", len(merged_meta), args.metadata_output)

    with open(args.sequences_output, "w") as fh:
        for seq_id, seq in merged_seqs.items():
            fh.write(f">{seq_id}\n{seq}\n")
    logger.info("Merged sequences: %d records → %s", len(merged_seqs), args.sequences_output)


if __name__ == "__main__":
    main()
