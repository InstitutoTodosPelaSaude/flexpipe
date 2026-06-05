#!/usr/bin/env python3
"""
Merge NCBI sequences with local/focal ITpS sequences.

Remote data source: NCBI (fetch_ncbi.py → accessionVersion / PPX column names)
Local focal data can be in two ITpS formats (auto-detected):
  - xlsx  (ITpS old format — header auto-detected by 'original_seq_id' row)
  - tsv   (ITpS new format — detected by 'ID' column, PascalCase headers)

Both ITpS formats are mapped to PPX column names so that curate.py can
handle NCBI and ITpS data uniformly.

The FASTA file is always the authority: only sequences present in the FASTA
are included from the local metadata.
"""

import argparse
import os
import sys

import pandas as pd
from Bio import SeqIO


# ITpS xlsx field → Pathoplexus PPX column name
XLSX_TO_PPX = {
    "original_seq_id":  "accessionVersion",
    "collection_date":  "sampleCollectionDate",
    "country":          "geoLocCountry",
    "state":            "geoLocAdmin1",
    "city":             "geoLocAdmin2",
    "host_species":     "hostNameCommon",
    "data_use":         "dataUseTerms",
    "authors":          "authors",
    "age":              "hostAge",
    "sex":              "hostGender",
    "specimen_id":      "specimenCollectorSampleId",
    "seq_instrument":   "sequencingInstrument",
    "seq_tech":         "sequencingProtocol",
    "depth_of_coverage": "depthOfCoverage",
    "sample_type":      "sampleType",
}

# ITpS new TSV format (PascalCase headers, 'ID' as identifier) → PPX column name
# Detected by presence of 'ID' column (absent in old xlsx and NCBI PPX formats)
ITPS_TSV_TO_PPX = {
    "ID":                          "accessionVersion",
    "CollectionDate":              "sampleCollectionDate",
    "Country":                     "geoLocCountry",
    "State":                       "geoLocAdmin1",
    "City":                        "geoLocAdmin2",
    "HostSpecies":                 "hostNameCommon",
    "DataUse":                     "dataUseTerms",
    "Authors":                     "authors",
    "HostAge":                     "hostAge",
    "HostSex":                     "hostGender",
    "OriginalSampleID":            "specimenCollectorSampleId",
    "SequenceInstrument":          "sequencingInstrument",
    "SequenceTechnology":          "sequencingProtocol",
    "DepthOfCoverage":             "depthOfCoverage",
    "SampleType":                  "sampleType",
    # Pass-through: rename to match RSV xlsx pass-through names that curate.py expects
    "AuthorAffiliations":          "affiliations",
    "OriginalLaboratoryName":      "orig_lab_name",
    "OriginalLaboratoryAddress":   "orig_lab_address",
    "SubmissionLaboratoryName":    "subm_lab_name",
    "SubmissionLaboratoryAddress": "subm_lab_address",
    "HostHealthState":             "health_state",
    "HostHealthOutcome":           "health_outcome",
    "HostSignsAndSymptoms":        "signs_and_symptoms",
    "HostDisease":                 "host_disease",
    "HostTravelHistory":           "travel_history",
    "PathogenSpecies":             "pathogen_common_name",
    "OriginalHostSpecimenID":      "sample_code",
}


def read_fasta_ids(path):
    return {rec.id.split()[0] for rec in SeqIO.parse(path, "fasta")}


def read_fasta_records(path):
    records = {}
    for rec in SeqIO.parse(path, "fasta"):
        sid = rec.id.split()[0]
        if sid not in records:
            records[sid] = str(rec.seq)
    return records


def read_xlsx_metadata(path):
    """Read ITpS xlsx, auto-detect header row, map columns to Pathoplexus names."""
    raw = pd.read_excel(path, header=None, dtype=str).fillna("")

    header_row = None
    for i, row in raw.iterrows():
        if "original_seq_id" in row.values:
            header_row = i
            break

    if header_row is None:
        print("ERROR: 'original_seq_id' column not found in xlsx.", file=sys.stderr)
        sys.exit(1)

    df = pd.read_excel(path, header=header_row, dtype=str).fillna("")
    df = df[df["original_seq_id"].str.strip() != ""].reset_index(drop=True)
    df = df.rename(columns={k: v for k, v in XLSX_TO_PPX.items() if k in df.columns})
    df["source"] = "ITpS"
    if "dataUseTerms" in df.columns:
        df["dataUseTerms"] = df["dataUseTerms"].str.strip().str.upper()
    return df


def read_itps_tsv_metadata(path):
    """Read ITpS new TSV format (PascalCase columns, 'ID' as identifier)."""
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False).fillna("")
    df = df.rename(columns={k: v for k, v in ITPS_TSV_TO_PPX.items() if k in df.columns})
    df["source"] = "ITpS"
    if "dataUseTerms" in df.columns:
        df["dataUseTerms"] = df["dataUseTerms"].str.strip().str.upper()
    # drop ViralQC output columns already present in the export — they'll be re-added
    # by curate.py after the pipeline's own ViralQC run
    vqc_cols = {
        "Segment", "Clade", "TargetGene", "GenomeQuality", "TargetRegionsQuality",
        "TargetGeneQuality", "CodingDNASequenceCoverageQuality", "MissingDataQuality",
        "PrivateMutationsQuality", "MixedSitesQuality",
        "SingleNucleotidePolymorphismsClustersQuality", "FrameShiftsQuality",
        "StopCodonsQuality", "Coverage", "CodingDNASequenceCoverage",
        "QualityOverallStatus", "NucleotideSubstitutions", "NucleotideDeletions",
        "NucleotideInsertions", "FrameShifts", "AminoacidSubstitutions",
        "AminoacidDeletions", "AminoacidInsertions", "TotalSubstitutions",
        "TotalDeletions", "TotalInsertions", "TotalFrameShifts", "TotalMissing",
        "TotalNonACGTNs", "TotalAminoacidSubstitutions", "TotalAminoacidDeletions",
        "TotalAminoacidInsertions", "TotalUnknownAminoacids",
        "PrivateNucleotideMutationsTotalReversionSubstitutions",
        "PrivateNucleotideMutationsTotalPrivateSubstitutions",
        "MissingDataStatus", "SingleNucleotidePolymorphismsClustersStatus",
        "FrameShiftsStatus", "StopCodonsStatus", "Dataset", "DatasetVersion",
        # already-renamed equivalents
        "clade", "genomeQuality", "coverage",
    }
    df.drop(columns=[c for c in vqc_cols if c in df.columns], inplace=True)
    return df


def read_local_metadata(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return read_xlsx_metadata(path)
    df_peek = pd.read_csv(path, sep="\t", dtype=str, nrows=0, keep_default_na=False)
    if "ID" in df_peek.columns and "original_seq_id" not in df_peek.columns \
            and "accessionVersion" not in df_peek.columns and "strain" not in df_peek.columns:
        return read_itps_tsv_metadata(path)
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False).fillna("")
    if "dataUseTerms" in df.columns:
        df["dataUseTerms"] = df["dataUseTerms"].str.strip().str.upper()
    return df


def detect_id_column(df):
    for col in ("accessionVersion", "strain"):
        if col in df.columns:
            return col
    raise ValueError(f"No ID column (accessionVersion/strain) found. Got: {list(df.columns)}")


def main():
    parser = argparse.ArgumentParser(description="Merge Pathoplexus and local sequences/metadata")
    parser.add_argument("--pathoplexus-metadata",  required=True)
    parser.add_argument("--pathoplexus-sequences", required=True)
    parser.add_argument("--local-metadata",        required=False, default="")
    parser.add_argument("--local-sequences",       required=False, default="")
    parser.add_argument("--enabled",               required=False, default="false")
    parser.add_argument("--metadata-output",       required=True)
    parser.add_argument("--sequences-output",      required=True)
    args = parser.parse_args()

    local_enabled = str(args.enabled).lower() in ("true", "1", "yes")

    os.makedirs(os.path.dirname(args.metadata_output), exist_ok=True)
    os.makedirs(os.path.dirname(args.sequences_output), exist_ok=True)

    # ── load remote (Pathoplexus or NCBI) data ────────────────────────────────
    print(f"Loading remote metadata: {args.pathoplexus_metadata}")
    ppx_meta = pd.read_csv(args.pathoplexus_metadata, sep="\t", dtype=str).fillna("")
    ppx_id_col = detect_id_column(ppx_meta)

    print(f"Loading remote sequences: {args.pathoplexus_sequences}")
    ppx_seqs = read_fasta_records(args.pathoplexus_sequences)
    print(f"  {len(ppx_meta)} metadata rows, {len(ppx_seqs)} sequences")

    merged_meta = ppx_meta.copy()
    merged_seqs = dict(ppx_seqs)

    # ── optionally merge local sequences ─────────────────────────────────────
    if local_enabled and args.local_metadata and args.local_sequences:
        if not os.path.isfile(args.local_metadata):
            print(f"WARNING: local metadata not found: {args.local_metadata}", file=sys.stderr)
        elif not os.path.isfile(args.local_sequences):
            print(f"WARNING: local sequences not found: {args.local_sequences}", file=sys.stderr)
        else:
            print(f"Loading local sequences: {args.local_sequences}")
            local_seqs = read_fasta_records(args.local_sequences)
            fasta_ids  = set(local_seqs)
            print(f"  {len(fasta_ids)} sequences in FASTA")

            print(f"Loading local metadata: {args.local_metadata}")
            local_meta = read_local_metadata(args.local_metadata)
            local_id_col = detect_id_column(local_meta)

            # filter metadata to sequences present in FASTA (FASTA is authoritative)
            before = len(local_meta)
            local_meta = local_meta[local_meta[local_id_col].isin(fasta_ids)].reset_index(drop=True)
            print(f"  {before} metadata rows → {len(local_meta)} matched to FASTA")

            # warn about FASTA IDs with no metadata
            missing = fasta_ids - set(local_meta[local_id_col])
            if missing:
                print(f"  WARNING: {len(missing)} FASTA IDs have no metadata entry:")
                for m in sorted(missing):
                    print(f"    {m}")

            # ensure Pathoplexus ID column exists in local metadata
            if local_id_col != ppx_id_col:
                local_meta[ppx_id_col] = local_meta[local_id_col]

            # deduplicate against Pathoplexus (avoid overwriting public sequences)
            existing_ids = set(ppx_meta[ppx_id_col])
            new_local_meta = local_meta[~local_meta[ppx_id_col].isin(existing_ids)].copy()
            new_local_seqs = {k: v for k, v in local_seqs.items()
                              if k not in existing_ids}
            print(f"  Adding {len(new_local_meta)} new local records")

            # outer concat: preserves all columns from both sources
            merged_meta = pd.concat([ppx_meta, new_local_meta], ignore_index=True).fillna("")
            merged_seqs.update(new_local_seqs)
    else:
        if local_enabled:
            print("local_sequences.enabled=true but paths not provided; skipping local merge")
        else:
            print("local_sequences.enabled=false; using only Pathoplexus data")

    # ── write outputs ─────────────────────────────────────────────────────────
    merged_meta.to_csv(args.metadata_output, sep="\t", index=False)
    print(f"\nMerged metadata: {len(merged_meta)} rows → {args.metadata_output}")

    with open(args.sequences_output, "w") as fh:
        for seq_id, seq in merged_seqs.items():
            fh.write(f">{seq_id}\n{seq}\n")
    print(f"Merged sequences: {len(merged_seqs)} records → {args.sequences_output}")


if __name__ == "__main__":
    main()
